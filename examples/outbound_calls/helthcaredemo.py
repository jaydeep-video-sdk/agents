import asyncio
import os
import logging
import json
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, AsyncIterator
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uvicorn
import httpx
import functools
from pyngrok import ngrok
import time

from videosdk.agents import (
    Agent,
    JobContext,
    function_tool,
    CascadingPipeline,
    ConversationFlow,
    WorkerJob,
    RoomOptions,
    AgentSession,
)
from videosdk.plugins.openai import OpenAISTT, OpenAILLM, OpenAITTS
from videosdk.plugins.deepgram import DeepgramSTT
from videosdk.plugins.elevenlabs import ElevenLabsTTS
from videosdk.plugins.silero import SileroVAD
from videosdk.plugins.turn_detector import VideoSDKTurnDetector, pre_download_videosdk_model
from videosdk.plugins.rnnoise import RNNoise
from videosdk.agents.event_bus import global_event_emitter

# --- Enhanced Logging Configuration ---

# Configure logging for STT and LLM debug information
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create specific loggers for STT and LLM operations
stt_logger = logging.getLogger("STT_DEBUG")
stt_logger.setLevel(logging.DEBUG)

llm_logger = logging.getLogger("LLM_DEBUG")
llm_logger.setLevel(logging.DEBUG)

# Create console handlers for STT and LLM loggers
stt_handler = logging.StreamHandler()
stt_handler.setLevel(logging.DEBUG)
stt_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stt_handler.setFormatter(stt_formatter)
stt_logger.addHandler(stt_handler)

llm_handler = logging.StreamHandler()
llm_handler.setLevel(logging.DEBUG)
llm_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
llm_handler.setFormatter(llm_formatter)
llm_logger.addHandler(llm_handler)

# Set main logger to INFO level to reduce noise
logging.getLogger().setLevel(logging.INFO)

load_dotenv()
pre_download_videosdk_model()

# --- Global State and API Config ---

# Simple in-memory storage for call details, mapping room_id to call info
CALL_INFO_MAP: Dict[str, Dict[str, Any]] = {}

# VideoSDK API configuration
VIDEOSDK_API_URL = "https://api.videosdk.live/v2"
VIDEOSDK_AUTH_TOKEN = os.getenv("VIDEOSDK_AUTH_TOKEN")


# --- Enhanced Google Sheets Integration ---

def setup_google_sheets():
    """Initializes connection to Google Sheets and returns worksheet objects."""
    log_sheet = None
    callback_sheet = None
    try:
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
        creds_file = "google-credentials.json"
        if not os.path.exists(creds_file):
            logger.error(f"'{creds_file}' not found. Google Sheets integration is disabled.")
            return None, None
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
        client = gspread.authorize(creds)
        sheet_name = os.getenv("GSPREAD_SHEET_NAME")
        if not sheet_name:
            logger.error("GSPREAD_SHEET_NAME env var not set. Google Sheets integration is disabled.")
            return None, None
        sheet = client.open(sheet_name)
        log_sheet = sheet.worksheet("Call-Logs")
        callback_sheet = sheet.worksheet("Callback-Requests")
        logger.info("✅ Google Sheets connected successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Google Sheets: {e}")
    return log_sheet, callback_sheet

log_sheet, callback_sheet = setup_google_sheets()


# --- Enhanced Conversation Flow ---

class MyCareConversationFlow(ConversationFlow):
    """Enhanced conversation flow for MyCare Health agent with detailed logging."""

    def __init__(self, agent: Agent):
        super().__init__(agent)

    async def run(self, transcript: str) -> AsyncIterator[str]:
        """Main conversation loop: handle a user turn and generate response."""
        stt_logger.debug(f"STT transcript received: '{transcript[:100]}{'...' if len(transcript) > 100 else ''}'")
        await self.on_turn_start(transcript)
        llm_logger.debug("LLM processing started")
        async for response_chunk in self.process_with_llm():
            llm_logger.debug(f"LLM response chunk: '{response_chunk[:100]}{'...' if len(response_chunk) > 100 else ''}'")
            yield response_chunk
        llm_logger.debug("LLM processing completed")
        await self.on_turn_end()

    async def on_turn_start(self, transcript: str) -> None:
        stt_logger.debug("STT turn started")
        self.is_turn_active = True

    async def on_turn_end(self) -> None:
        stt_logger.debug("STT turn ended")
        self.is_turn_active = False

    def on_speech_started(self) -> None: pass
    def on_speech_stopped(self) -> None: pass


# --- Agent and Pipeline Definition ---

def create_agent_pipeline():
    """Create the cascading pipeline with all components."""
    logger.info("Creating cascading pipeline with Deepgram STT, OpenAI LLM, and ElevenLabs TTS")
    
    try:
        logger.info("Initializing pipeline components...")
        stt = DeepgramSTT(api_key=os.getenv("DEEPGRAM_API_KEY"), model="nova-3", language="multi")
        logger.info("✅ Deepgram STT provider created successfully")

        llm = OpenAILLM(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o-2024-08-06")
        logger.info("✅ OpenAI LLM provider created successfully")

        tts = ElevenLabsTTS(api_key=os.getenv("ELEVENLABS_API_KEY"), voice="gHu9GtaHOXcSqFTK06ux", speed=1.2, enable_streaming=True)
        logger.info("✅ ElevenLabs TTS provider created successfully")

        vad = SileroVAD(threshold=0.3, min_speech_duration=0.05, min_silence_duration=0.50)
        turn_detector = VideoSDKTurnDetector(threshold=0.8)
        denoise = RNNoise()

        pipeline = CascadingPipeline(
            stt=stt, 
            llm=llm, 
            tts=tts, 
            vad=vad, 
            turn_detector=turn_detector, 
            denoise=denoise
        )
        logger.info("✅ Cascading pipeline created successfully")
        return pipeline

    except Exception as e:
        logger.error(f"❌ Failed to create pipeline: {e}")
        raise

class MyCareAgent(Agent):
    """MyCare Health agent for patient follow-up calls."""

    def __init__(self, ctx: JobContext, agent_config: Dict[str, Any]):
        self.ctx = ctx
        self.room_id = ctx.room_options.room_id
        
        # Get the number and patient name directly from the config passed at creation.
        self.caller_number = agent_config.get("to_number", "Unknown")
        self.patient_name = agent_config.get("patient_name", "Valued Patient")
        self.call_id = "N/A" # Will be populated later if possible.

        self.greeting_message: Optional[str] = None
        self._participant_left_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()

        super().__init__(
            instructions="""
**<OVERALL_CONTEXT>**
You are "Maya," an advanced AI Care Coordinator for MyCare Health. Your purpose is to conduct empathetic, professional, and effective follow-up calls to patients who have recently had an appointment or been discharged. You are a crucial extension of our care team, designed to ensure our patients feel supported and safe during their recovery. Your goal is not to follow a script, but to achieve a set of objectives within a natural, human-like conversation.

**</AGENT_PERSONA: MAYA>**

*   **Identity:** You are Maya, a Care Coordinator. You are a trusted partner in the patient's recovery journey, but you are **not** a medical professional.
*   **Core Personality:** You are the embodiment of calm confidence. You are warm, empathetic, patient, and meticulously reliable. Make sure to converse in English.
*   **Vocal Style & Pacing (Inspired by ElevenLabs Controls):**
    *   **(style: conversational, empathetic)** Your delivery should be relaxed and unhurried, with a naturally warm and gentle vocal quality.
    *   **Use Pauses for Effect:** Employ natural pauses (using commas, ellipses..., and dashes—) to make your speech feel more considered and less robotic. This is especially important when asking how a patient is feeling. For example: "I'm calling to see... how have you been feeling since your visit?"
    *   **Empathetic Intonation:** Your tone should reflect active listening. When a patient expresses a concern, your response should be softer and more deliberate. When they report good news, your tone should be genuinely positive and encouraging.
    *   **Clarity Above All:** Speak in simple, clear language. Avoid jargon. The goal is to make the patient feel comfortable and understood.

**<INTERACTION_STYLE: Filling Silence>**
*   **Acknowledge Before Acting:** Before you use a tool like `schedule_callback` or `log_call_disposition`, you MUST first inform the user what you are doing with a short, reassuring message. This is critical for a smooth conversation.
    *   **Example for scheduling:** "Of course. Let me just pull up the schedule for you, one moment..." (Then call the tool).
    *   **Example for logging/ending:** "I've made a note of that. Thank you for your time today." (Then call `log_call_disposition` and/or `end_call`).
*   **Confirm After Acting:** After a tool runs successfully, confirm its completion to the user.
    *   **Example:** "Okay, I have that scheduled for you. A nurse will call you back this afternoon."

**<CORE_DIRECTIVE: THE GOLDEN RULE>**
**You MUST NOT, under any circumstances, provide medical advice, interpret symptoms, or offer a diagnosis.** Your sole function when faced with a medical question is to act as a bridge to a qualified clinician. Acknowledging this limitation is a core part of your identity and builds trust.

**<MANDATORY_PROTOCOLS>**

1.  **Emergency Protocol:** If a patient mentions symptoms of a potential medical emergency (e.g., severe chest pain, difficulty breathing, sudden confusion, uncontrolled bleeding), you must **immediately and calmly** interrupt the conversation and deliver this exact response:
    > "Based on what you're describing, it is very important that you hang up this call and dial 911 for immediate medical help. Please do so now."

2.  **No Competitor Discussion:** You must not mention, compare, or acknowledge any other hospitals, clinics, or healthcare providers. Your focus is exclusively on the patient's care through MyCare Health.
    > *Polite Deflection:* "I can only speak about the care and services we provide here at MyCare Health, as our main focus is making sure your personal recovery is on track."

3.  **Privacy and Confidentiality:** Always operate with the understanding that the conversation is private and protected.

**<CONVERSATIONAL_FRAMEWORK: A Freeflow Guide>**

Your goal is to have a natural conversation that covers the necessary points. You do not need to follow a rigid order.

**Primary Objective:** To assess the patient's recovery and well-being, and to determine if a clinical callback is needed.

**Key Check-in Topics (Your Mental Checklist):**
*   General well-being and mood.
*   Medication adherence and any related issues.
*   New or worsening symptoms.
*   Understanding of their care plan (diet, activity).
*   Status of follow-up appointments.

---

**CONVERSATIONAL TOOLKIT (Building Blocks for a Natural Conversation):**

*   **1. The Opening:** Start warm and clear.
    > "Hi, may I speak with [Patient Name]? ... Hi, [Patient Name], my name is Maya, and I'm a Care Coordinator from MyCare Health. I'm just calling to check in on you after your recent visit — do you have a few minutes to chat?"

*   **2. Active Listening & Validation:** This is your most important skill. Listen to the patient's words and the emotion behind them, and reflect it back to them.
    > *If Patient says:* "I'm feeling pretty good, actually."
    > *Your Response:* "That is wonderful to hear. I'm so glad your recovery is going well."
    >
    > *If Patient says:* "I'm just a bit worried about this new pill."
    > *Your Response:* "I can certainly understand that. It's completely normal to have questions about a new medication, and it's good that you're paying close attention."

*   **3. Natural Transitions & Pivoting:** Use smooth transitions to move between topics.
    > "I'm glad to hear the new medication isn't giving you any trouble. And how are you feeling overall? Any new or concerning symptoms?"
    > "That makes sense. Well, besides the appointment scheduling, is there anything else on your mind regarding your recovery plan?"

*   **4. The Clinical Handoff (Your Core Action):** When a medical question arises, transition seamlessly to the solution.
    > "That's a really important question, and the best person to answer it would be one of our nurses. **While I'm not qualified to give medical advice,** I can schedule a callback for you right away. Would you like me to do that?"

*   **5. The Closing:** End the call with clarity and warmth.
    *   **If no issues:** "It has been wonderful speaking with you, and I'm so pleased to hear you're doing well. I'll make a positive note in your chart. Please remember you can always call our office if anything comes up. Have a great day!"
    *   **If callback scheduled:** "Okay, I have that scheduled. A nurse will be calling you back [this afternoon/tomorrow morning]. Is there anything else I can assist you with before I let you go? ... Great. Take care, and we'll be in touch soon."

**</TOOL_USAGE_GUIDELINES>**

*   **`log_call_disposition`:** Use this at the end of every call to record the outcome (e.g., 'Completed - No Issues', 'Callback Scheduled - Medication Question'). This is a mandatory final step.
*   **`schedule_callback`:** Only use this tool after the patient has explicitly agreed to a callback from a clinician.
*   **`end_call`:** Use this tool to terminate the conversation gracefully after all objectives are met and the call is logged.
"""
        )

    async def on_enter(self) -> None:
        logger.info(f"[{self.room_id}] Agent session started for number: {self.caller_number}")
        # Try to grab the call_id if it becomes available in the map.
        call_info = CALL_INFO_MAP.get(self.room_id)
        if call_info:
            self.call_id = call_info.get("call_id", "N/A")
        
        self.greeting_message = f"Hi {self.patient_name}, my name is Maya, and I'm a Care Coordinator from MyCare Health. This call will be recorded for training and quality assurance purposes. Do you have a few minutes to talk?"

    async def on_exit(self) -> None:
        logger.info(f"[{self.room_id}] Agent session ended.")

    async def greet_user(self):
        logger.info(f"[{self.room_id}] Participant stream enabled. Greeting user.")
        if self.greeting_message:
            await self.session.say(self.greeting_message)

    def participant_left(self):
        logger.info(f"[{self.room_id}] Participant has left the call.")
        self._participant_left_event.set()

    async def wait_for_call_end(self):
        # Create tasks from the event wait coroutines.
        participant_left_task = asyncio.create_task(self._participant_left_event.wait())
        shutdown_task = asyncio.create_task(self._shutdown_event.wait())
        
        await asyncio.wait(
            [participant_left_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        logger.info(f"[{self.room_id}] Call end condition met.")

    @function_tool
    async def log_call_disposition(self, disposition: str, notes: str = "") -> dict:
        """
        Log the final disposition of the call.
        Args:
            disposition: The outcome of the call (e.g., 'Completed - No Issues', 'Callback Scheduled', 'Voicemail Left', 'Patient Concerned')
            notes: Additional notes about the call, such as specific patient concerns or feedback.
        """
        if not log_sheet:
            return {"status": "error", "message": "Google Sheets not available."}
        try:
            # Best-effort to get the latest call_id if it was added after on_enter
            if self.call_id == 'N/A' and self.room_id in CALL_INFO_MAP:
                self.call_id = CALL_INFO_MAP[self.room_id].get('call_id', 'N/A')

            logger.info(f"[{self.room_id}] Logging call disposition to Google Sheets: {disposition}")
            human_readable_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = [human_readable_time, self.caller_number, self.patient_name, self.call_id, disposition, notes]
            # Check if header row exists, if not, create it
            header = ["Timestamp", "Patient Number", "Patient Name", "Call ID", "Disposition", "Notes"]
            if not log_sheet.get_all_values():
                log_sheet.append_row(header)
            log_sheet.append_row(log_entry)
            return {"status": "success", "message": "Call disposition logged."}
        except Exception as e:
            logger.error(f"Failed to log call disposition: {e}")
            return {"status": "error", "message": str(e)}

    @function_tool
    async def schedule_callback(self, reason: str, time_details: str) -> dict:
        """
        Schedules a callback for the user with a clinician.
        Args:
            reason: The reason for the callback (e.g., 'Medication Question', 'Worsening Symptoms').
            time_details: A string describing when the callback should occur (e.g., 'This afternoon', 'Tomorrow morning').
        """
        if not callback_sheet:
            return {"status": "error", "message": "Google Sheets not available."}
        try:
            if self.call_id == 'N/A' and self.room_id in CALL_INFO_MAP:
                self.call_id = CALL_INFO_MAP[self.room_id].get('call_id', 'N/A')

            logger.info(f"[{self.room_id}] Scheduling callback for {self.caller_number} due to: {reason}")
            human_readable_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            callback_entry = [human_readable_time, self.caller_number, self.patient_name, self.call_id, reason, time_details, "Pending"]
            # Check if header row exists, if not, create it
            header = ["Request Timestamp", "Patient Number", "Patient Name", "Call ID", "Callback Reason", "Requested Time", "Status"]
            if not callback_sheet.get_all_values():
                callback_sheet.append_row(header)
            callback_sheet.append_row(callback_entry)
            return {"status": "success", "message": f"Callback scheduled. A clinician will call back {time_details}."}
        except Exception as e:
            logger.error(f"Failed to schedule callback: {e}")
            return {"status": "error", "message": str(e)}

    @function_tool
    async def end_call(self, reason: str = "Call completed") -> dict:
        """
        End the current call.
        Args:
            reason: Reason for ending the call.
        """
        logger.info(f"[{self.room_id}] Agent initiating end of call: {reason}")
        await self.log_call_disposition("Call Ended by Agent", reason)
        
        if not self._shutdown_event.is_set():
            self._shutdown_event.set()

        return {"status": "success", "message": "Call ending."}


# --- Agent Lifecycle Management ---

async def agent_entrypoint(ctx: JobContext, agent_config: Dict[str, Any]):
    meeting_id = ctx.room_options.room_id
    logger.info(f"[{meeting_id}] 📞 Starting agent entrypoint")
    
    session = None
    on_stream_enabled = None
    on_participant_left = None

    try:
        pipeline = create_agent_pipeline()
        agent = MyCareAgent(ctx, agent_config=agent_config)
        
        # Use enhanced conversation flow
        session = AgentSession(
            agent=agent,
            pipeline=pipeline,
            conversation_flow=MyCareConversationFlow(agent),
        )
        
        await ctx.connect()
        logger.info(f"[{meeting_id}] Agent context connected.")
        
        await session.start() 
        logger.info(f"[{meeting_id}] Agent session started.")

        # Define event handlers BEFORE registering them
        def on_stream_enabled(data):
            logger.info(f"[{meeting_id}] AUDIO_STREAM_ENABLED event received: {data}")
            asyncio.create_task(agent.greet_user())

        def on_participant_left(data):
            logger.info(f"[{meeting_id}] PARTICIPANT_LEFT event received: {data}")
            agent.participant_left()

        # Register event handlers
        global_event_emitter.on("AUDIO_STREAM_ENABLED", on_stream_enabled)
        global_event_emitter.on("PARTICIPANT_LEFT", on_participant_left)
        logger.info(f"[{meeting_id}] Event handlers registered")

        # Signal that agent is ready
        signal_agent_ready(meeting_id)
        logger.info(f"[{meeting_id}] Agent ready signal sent")
        
        # Wait for call to end
        await agent.wait_for_call_end()

    except Exception as e:
        logger.error(f"[{meeting_id}] 💥 EXCEPTION in agent job: {e}", exc_info=True)
    finally:
        # Clean up event handlers
        try:
            if on_stream_enabled:
                global_event_emitter.off("STREAM_ENABLED", on_stream_enabled)
                logger.info(f"[{meeting_id}] STREAM_ENABLED handler removed")
            if on_participant_left:
                global_event_emitter.off("PARTICIPANT_LEFT", on_participant_left)
                logger.info(f"[{meeting_id}] PARTICIPANT_LEFT handler removed")
        except Exception as cleanup_error:
            logger.error(f"[{meeting_id}] Error during event handler cleanup: {cleanup_error}")

        # Clean up session and context
        if session:
            try:
                await session.close()
                logger.info(f"[{meeting_id}] Session closed")
            except Exception as session_error:
                logger.error(f"[{meeting_id}] Error closing session: {session_error}")
        
        try:
            await ctx.shutdown()
            logger.info(f"[{meeting_id}] Context shutdown")
        except Exception as ctx_error:
            logger.error(f"[{meeting_id}] Error shutting down context: {ctx_error}")
        
        # Clean up global state
        if meeting_id in CALL_INFO_MAP:
            del CALL_INFO_MAP[meeting_id]
            logger.info(f"[{meeting_id}] Removed from CALL_INFO_MAP")
        
        if os.path.exists(f"/tmp/agent_ready_{meeting_id}"):
            os.remove(f"/tmp/agent_ready_{meeting_id}")
            logger.info(f"[{meeting_id}] Agent ready file removed")

        logger.info(f"[{meeting_id}] 🧼 Agent job cleanup complete.")

def signal_agent_ready(room_id: str):
    with open(f"/tmp/agent_ready_{room_id}", "w") as f:
        f.write("ready")


# --- VideoSDK and SIP API Functions ---

async def create_videosdk_room() -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{VIDEOSDK_API_URL}/rooms",
            headers={
                "Authorization": f"{VIDEOSDK_AUTH_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "geofence": {
                    "region": "us002"
                }
            }
        )
        response.raise_for_status()
        return response.json()["roomId"]

async def start_sip_call(contact_number: str, meeting_id: str):
    gateway_id = os.getenv("VIDEOSDK_OUTBOUND_ID")
    if not gateway_id:
        raise ValueError("VIDEOSDK_OUTBOUND_ID environment variable not set.")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{VIDEOSDK_API_URL}/sip/call/",
            headers={"Authorization": VIDEOSDK_AUTH_TOKEN, "Content-Type": "application/json"},
            json={"gatewayId": gateway_id, "sipCallTo": contact_number, "destinationRoomId": meeting_id},
        )
        response.raise_for_status()
        return response.json()

async def wait_for_agent_ready(room_id: str, timeout: int = 30) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.path.exists(f"/tmp/agent_ready_{room_id}"):
            return True
        await asyncio.sleep(0.5)
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MyCare Health SIP AI Agent")
    port = int(os.getenv("PORT", 8000))
    ngrok_auth_token = os.getenv("NGROK_AUTHTOKEN")
    
    public_url = None
    if ngrok_auth_token:
        ngrok.set_auth_token(ngrok_auth_token)
        try:
            tunnel = ngrok.connect(port, "http")
            public_url = tunnel.public_url
            logger.info(f"Ngrok tunnel active: {public_url}")
        except Exception as e:
            logger.error(f"Failed to start ngrok: {e}")
    
    logger.info(f"Using public URL: {public_url}")
    yield

    if public_url:
        ngrok.kill()
        logger.info("Ngrok tunnel closed.")
    logger.info("Shutting down MyCare Health SIP AI Agent")


app = FastAPI(title="VideoSDK MyCare Health Call API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class CallRequest(BaseModel):
    to_number: str
    patient_name: str
    class Config:
        json_schema_extra = {
            "example": {
                "to_number": "+15551234567", 
                "patient_name": "Krish"
            }
        }


def _make_context(meeting_id: str) -> JobContext:
    return JobContext(
        room_options=RoomOptions(room_id=meeting_id, name="MyCare AI Call")
    )

@app.post("/sip/answer/{room_id}", include_in_schema=False)
async def answer_call(room_id: str, request: Request):
    """Handle SIP answer webhook - uses SIP plugin's built-in functionality."""
    logger.info(f"Answering call for room: {room_id}")
    
    try:
        # Import the SIP plugin functionality
        from videosdk.plugins.sip import create_sip_manager
        
        # Get required environment variables
        auth_token = os.getenv("VIDEOSDK_AUTH_TOKEN")
        if not auth_token:
            raise ValueError("VIDEOSDK_AUTH_TOKEN not found in environment variables")
        
        # Create SIP manager with Twilio provider
        sip_manager = create_sip_manager(
            provider="twilio",
            videosdk_token=auth_token,
            provider_config={
                "account_sid": os.getenv("TWILIO_ACCOUNT_SID"),
                "auth_token": os.getenv("TWILIO_AUTH_TOKEN"),
                "phone_number": os.getenv("TWILIO_PHONE_NUMBER"),
            }
        )
        
        # Get the SIP response for the room using built-in functionality
        response_body, status_code, headers = sip_manager.get_sip_response_for_room(room_id)
        logger.info(f"✅ Call answered successfully for room: {room_id}")
        return Response(content=response_body, status_code=status_code, headers=headers)
    
    except Exception as e:
        logger.error(f"Error answering call: {e}")
        return Response(content="An error occurred", status_code=500)

@app.post("/call/make")
async def make_call(payload: CallRequest):
    if not VIDEOSDK_AUTH_TOKEN:
        return {"status": "error", "message": "VIDEOSDK_AUTH_TOKEN not found"}
    
    try:
        meeting_id = await create_videosdk_room()
        logger.info(f"Created VideoSDK room: {meeting_id}")

        # Pass the phone number and patient name from the payload directly into the agent's config.
        agent_config = {
            "patient_name": payload.patient_name, 
            "to_number": payload.to_number
        }
        context_factory = functools.partial(_make_context, meeting_id)
        job_entrypoint = functools.partial(agent_entrypoint, agent_config=agent_config)
        
        job = WorkerJob(entrypoint=job_entrypoint, jobctx=context_factory)
        job.start()
        
        logger.info(f"[CALL_MAKE] Agent job started for room: {meeting_id}. Waiting for agent to be ready...")

        if await wait_for_agent_ready(meeting_id):
            logger.info(f"[{meeting_id}] Agent is ready. Making SIP call to {payload.to_number}")
            sip_response = await start_sip_call(payload.to_number, meeting_id)
            
            # Update the map with the full details from the SIP response.
            call_data = sip_response.get("data", {})
            CALL_INFO_MAP[meeting_id] = {
                "call_id": call_data.get("id"),
                "caller_number": call_data.get("to") # This confirms the number.
            }

            logger.info(f"[{meeting_id}] SIP call initiated successfully. Call ID: {call_data.get('id')}")
            return {"status": "call_initiated", "meeting_id": meeting_id, "call_id": call_data.get("id")}
        else:
            logger.error(f"[{meeting_id}] Agent failed to become ready in time.")
            return {"status": "error", "message": "Agent failed to initialize."}

    except Exception as e:
        logger.error(f"Error in make_call: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)