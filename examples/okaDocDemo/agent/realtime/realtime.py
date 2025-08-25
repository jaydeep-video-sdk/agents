import asyncio, os, sys
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

sys.path.append(str(Path(__file__).parent.parent.parent))
from videosdk.agents import Agent, AgentSession, RealTimePipeline, JobContext, RoomOptions, WorkerJob, function_tool
from videosdk.plugins.google import GeminiRealtime, GeminiLiveConfig
from api.room_api import VideoSDKRoomClient
from api.google_sheet_api import GoogleSheetClient
from api.sip_api import VideoSDKSIPClient

_GLOBAL_CONFIG = None
@dataclass
class ModelConfig:
    model: str = "gemini-2.0-flash-live-001"
    api_key: str = None
    voice: str = "Leda"
    response_modalities: list = None
    
    def __post_init__(self):
        if self.response_modalities is None:
            self.response_modalities = ["AUDIO"]
        if self.api_key is None:
            self.api_key = os.getenv("GOOGLE_API_KEY")

@function_tool
async def schedule_appointment_tool(patient_name: str, phone: str, preferred_date: str, preferred_time: str, reason: str) -> dict:
    """Schedule a medical appointment by adding it to Google Sheets"""
    try:
        sheet_id = "1hEGoadbZ5XCFRWMJ8yS-VVlaNrLAG_yb2AUeMFcDQ3Y"
        creds_path = os.path.join(os.path.dirname(__file__), "..", "..", "api", "arctic-dynamo-469411-g9-3b97d92e4cc2.json")
        
        client = GoogleSheetClient(sheet_id, creds_path)
        
        appointment_id = f"APT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        appointment_data = [
            appointment_id,
            patient_name,
            phone,
            preferred_date,
            preferred_time,
            reason,
            "Scheduled",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
        
        response = client.create_row(appointment_data)
        
        if response.success:
            return {
                "status": "success",
                "message": f"Appointment scheduled successfully! Your appointment ID is {appointment_id}. We'll contact you at {phone} to confirm the appointment for {preferred_date} at {preferred_time}.",
                "appointment_id": appointment_id,
                "patient_name": patient_name,
                "phone": phone,
                "preferred_date": preferred_date,
                "preferred_time": preferred_time
            }
        else:
            return {
                "status": "error",
                "message": f"Sorry, there was an error scheduling your appointment: {response.error}"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Sorry, I couldn't schedule your appointment right now. Please try again later. Error: {str(e)}"
        }


@dataclass
class AgentConfig:
    instructions: str = "You are a professional healthcare assistant. You can help patients schedule medical appointments and make outbound calls for healthcare consultations. Always be empathetic and professional. When scheduling appointments, collect patient name, phone, preferred date/time, and reason. You can also initiate calls to patients when needed."
    greeting: str = "Hello! I'm your healthcare assistant. I can help you schedule medical appointments and make calls to patients for consultations. What can I do for you today?"
    farewell: str = "Thank you for using our healthcare services. Take care and have a healthy day!"
    tools: list = None
    
    def __post_init__(self):
        if self.tools is None:
            self.tools = [schedule_appointment_tool]

@dataclass
class RoomConfig:
    name: str = "VideoSDK Realtime Agent"
    playground: bool = True

@dataclass
class PipelineConfig:
    model_config: ModelConfig
    agent_config: AgentConfig
    room_config: RoomConfig

class HealthcareVoiceAgent(Agent):
    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig()
        
        self.config = config
        self.current_room_id = None
        super().__init__(instructions=config.instructions, tools=config.tools)
    
    async def on_enter(self): 
        await self.session.say(self.config.greeting)
    
    async def on_exit(self): 
        await self.session.say(self.config.farewell)
    async def on_call(self):
        await self.session.say("Thank you for calling me. I'm here to help you with your appointment.")
    async def on_call_end(self):
        await self.session.say("Thank you for your call. Have a great day!")

async def start_session_configured(context: JobContext):
    global _GLOBAL_CONFIG
    
    if _GLOBAL_CONFIG is None:
        return await start_session(context)
    
    config = _GLOBAL_CONFIG
    
    # Store room ID in global config
    room_id = None
    if hasattr(context, 'room_options') and context.room_options:
        room_id = context.room_options.room_id
        config._current_room_id = room_id
        print(f"🏠 Room created with ID: {room_id}")
    else:
        print("❌ No room ID found in context")
    
    # Make SIP call FIRST before any agent initialization
    print("📞 Starting SIP call process...")
    if room_id:
        print(f"📞 Making SIP call to room: {room_id}")
        await _make_sip_call(room_id)
        print("📞 SIP call process completed")
    else:
        print("❌ Cannot make SIP call - no room ID available")
    
    model = GeminiRealtime(
        model=config.model_config.model,
        api_key=config.model_config.api_key,
        config=GeminiLiveConfig(
            voice=config.model_config.voice,
            response_modalities=config.model_config.response_modalities
        )
    )

    pipeline = RealTimePipeline(model=model)
    agent = HealthcareVoiceAgent(config.agent_config)
    session = AgentSession(agent=agent, pipeline=pipeline)

    try:
        print(f"🤖 Agent connecting to room: {context.room_options.room_id}")
        await context.connect()
        print("✅ Agent connected to room successfully")
        
        print("🚀 Starting agent session...")
        await session.start()
        print("✅ Agent session started - ready to talk!")
        
        await asyncio.Event().wait()
    except Exception as e:
        print(f"❌ Error in session: {str(e)}")
        if "quota" in str(e).lower() or "billing" in str(e).lower():
            print("🔴 Google API quota exceeded. Please check:")
            print("   1. Your Google Cloud billing is enabled")
            print("   2. Your API key has sufficient quota")
            print("   3. Your Gemini API usage limits")
            print("💡 SIP call was successful, but agent can't start due to quota")
        else:
            print(f"🔴 Agent failed to join room {context.room_options.room_id}")
        raise e
    finally:
        await session.close()
        await context.shutdown()

async def _make_sip_call(room_id: str):
    """Make SIP call directly to the room"""
    print(f"🔄 _make_sip_call function called with room_id: {room_id}")
    try:
        gateway_id = "abe274e7-bb07-4fae-90f7-85d7f707434f"
        target_number = "+919664920749"
        
        print(f"📞 Initiating SIP call to {target_number} using gateway {gateway_id} for room {room_id}")
        
        sip_client = VideoSDKSIPClient()
        print("✅ SIP client created successfully")
        
        print("📞 Triggering SIP call...")
        call_response = sip_client.trigger_call(
            gateway_id=gateway_id,
            sip_call_to=target_number,
            destination_room_id=room_id,
            participant_name="Patient",
            wait_until_answered=True,
            ringing_timeout=30,
            max_call_duration=600
        )
        print(f"✅ SIP call triggered successfully: {call_response}")
        return call_response
    except Exception as e:
        print(f"❌ Error making SIP call: {str(e)}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return None

def make_context_configured() -> JobContext:
    global _GLOBAL_CONFIG
    
    if _GLOBAL_CONFIG is None:
        return make_context()
    
    config = _GLOBAL_CONFIG
    
    print("🏠 Creating room...")
    with VideoSDKRoomClient() as room_client:
        response = room_client.create_room()
        
        if not response.success or not response.data:
            raise Exception(f"Room creation failed: {response.error or 'Unknown error'}")
        
        room_id = response.data.get('roomId')
        if not room_id:
            raise Exception("Room creation failed: No room ID returned")
    
    print(f"✅ Room created successfully: {room_id}")
    
    # Make SIP call IMMEDIATELY after room creation, before any agent setup
    print("📞 Making SIP call immediately after room creation...")
    _make_sip_call_sync(room_id)
    
    room_options = RoomOptions(
        room_id=room_id,
        name=config.room_config.name,
        playground=config.room_config.playground
    )

    return JobContext(room_options=room_options)

class ConfigBuilder:
    def __init__(self):
        self.model_config = ModelConfig()
        self.agent_config = AgentConfig()
        self.room_config = RoomConfig()
    
    def with_model(self, model: str = None, api_key: str = None, voice: str = None, response_modalities: list = None):
        if model: self.model_config.model = model
        if api_key: self.model_config.api_key = api_key
        if voice: self.model_config.voice = voice
        if response_modalities: self.model_config.response_modalities = response_modalities
        return self
    
    def with_agent(self, instructions: str = None, greeting: str = None, farewell: str = None, tools: list = None):
        if instructions: self.agent_config.instructions = instructions
        if greeting: self.agent_config.greeting = greeting
        if farewell: self.agent_config.farewell = farewell
        if tools: self.agent_config.tools = tools
        return self
    
    def with_room(self, name: str = None, playground: bool = None):
        if name: self.room_config.name = name
        if playground is not None: self.room_config.playground = playground
        return self
    
    def build(self) -> PipelineConfig:
        return PipelineConfig(
            model_config=self.model_config,
            agent_config=self.agent_config,
            room_config=self.room_config
        )

def run_with_config(config: PipelineConfig):
    global _GLOBAL_CONFIG
    _GLOBAL_CONFIG = config
    
    job = WorkerJob(entrypoint=start_session_configured, jobctx=make_context_configured)
    job.start()

def run_default():
    global _GLOBAL_CONFIG
    _GLOBAL_CONFIG = None
    
    job = WorkerJob(entrypoint=start_session, jobctx=make_context)
    job.start()

async def start_session(context: JobContext):
    model = GeminiRealtime(
        model="gemini-2.0-flash-live-001",
        api_key=os.getenv("GOOGLE_API_KEY"), 
        config=GeminiLiveConfig(           
            voice="Leda",
            response_modalities=["AUDIO"]
        )
    )

    pipeline = RealTimePipeline(model=model)

    session = AgentSession(agent=HealthcareVoiceAgent(),pipeline=pipeline)

    try:
        await context.connect()
        await session.start()
        await asyncio.Event().wait()
    finally:
        await session.close()
        await context.shutdown()

def make_context() -> JobContext:
    print("🏠 Creating room...")
    with VideoSDKRoomClient() as room_client:
        response = room_client.create_room()
        
        if not response.success or not response.data:
            raise Exception(f"Room creation failed: {response.error or 'Unknown error'}")
        
        room_id = response.data.get('roomId')
        if not room_id:
            raise Exception("Room creation failed: No room ID returned")
    
    print(f"✅ Room created successfully: {room_id}")
    
    # Make SIP call IMMEDIATELY after room creation, before any agent setup
    print("📞 Making SIP call immediately after room creation...")
    _make_sip_call_sync(room_id)
    
    room_options = RoomOptions(
        room_id=room_id,
        name="VideoSDK Realtime Agent",
        playground=True
    )

    return JobContext(room_options=room_options)

def _make_sip_call_sync(room_id: str):
    """Synchronous wrapper for SIP call"""
    print(f"🔄 Making SIP call to room: {room_id}")
    try:
        gateway_id = "9908f984-fd53-433d-b192-3895e6a2d3e0"
        target_number = "+919664920749"
        
        print(f"📞 Calling {target_number} to join room {room_id}")
        
        sip_client = VideoSDKSIPClient()
        print("✅ SIP client created")
        
        call_response = sip_client.trigger_call(
            gateway_id=gateway_id,
            sip_call_to=target_number,
            destination_room_id=room_id,
            participant_name="Patient",
            wait_until_answered=True,
            ringing_timeout=30,
            max_call_duration=600
        )
        
        print(f"✅ SIP call triggered successfully: {call_response}")
        return call_response
        
    except Exception as e:
        print(f"❌ Error making SIP call: {str(e)}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return None

if __name__ == "__main__":
    config = ConfigBuilder() \
        .with_model(voice="Leda", response_modalities=["AUDIO"]) \
        .with_agent(
            instructions="You are a professional healthcare assistant. You can help patients schedule medical appointments and make outbound calls for healthcare consultations. Always be empathetic and professional. When scheduling appointments, collect patient name, phone, preferred date/time, and reason. You can also initiate calls to patients when needed.",
            greeting="Hello! I'm your healthcare assistant. I can help you schedule medical appointments and make calls to patients for consultations. What can I do for you today?",
            farewell="Thank you for using our healthcare services. Take care and have a healthy day!",
            tools=[schedule_appointment_tool]
        ) \
        .with_room(name="Healthcare Assistant", playground=True) \
        .build()
    
    run_with_config(config)