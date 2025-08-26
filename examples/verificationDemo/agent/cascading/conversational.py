import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional,AsyncIterator
from dataclasses import dataclass
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set to INFO to reduce verbosity
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Set log level for all loggers
logging.getLogger().setLevel(logging.INFO)

# Get logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Set higher log levels for verbose modules
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('videosdk').setLevel(logging.INFO)
logging.getLogger('aioice').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
load_dotenv(dotenv_path=env_path)

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent.parent  # Go up to verificationDemo
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add parent directory to path for absolute imports
if str(project_root.parent) not in sys.path:
    sys.path.insert(0, str(project_root.parent))

from videosdk.agents import (
    Agent,
    AgentSession,
    RealTimePipeline,
    JobContext,
    WorkerJob,
    RoomOptions,
    CascadingPipeline,
    ConversationFlow,
    ChatRole,
)
from videosdk.plugins.google import (
    GoogleSTT,
    GoogleLLM,
    GoogleTTS,
    GeminiRealtime,
    GeminiLiveConfig
)
from videosdk.plugins.silero import SileroVAD
from videosdk.plugins.turn_detector import TurnDetector
from examples.verificationDemo.api.room_api import VideoSDKRoomClient
from examples.verificationDemo.api.sip_api import VideoSDKSIPClient


@dataclass
class SimpleConfig:
    """Simplified configuration for the voice agent"""
    # Model settings
    model: str = "gemini-2.0-flash-live-001"
    voice: str = "Leda"
    language: str = "hi-IN"
    
    # Agent settings
    instructions: str = "You are a professional verification agent from ABC Bank. Be polite and efficient."
    greeting: str = "Namaskar ji! Main Priya bol rahi hun ABC Bank se... aap kaise hain?"
    farewell: str = "Bahut dhanyawaad ji aapke time ke liye. Apka din shubh ho!"
    
    # Call settings
    auto_dial: bool = False
    target_number: Optional[str] = None
    room_name: str = "ABC Bank Verification"
    
    def __post_init__(self):
        if not self.target_number:
            self.target_number = os.getenv("TARGET_PHONE_NUMBER")


class BankingVerificationFlow(ConversationFlow):
    """Simple banking verification conversation flow"""
    
    def __init__(self, agent, stt=None, llm=None, tts=None, vad=None, turn_detector=None):
        super().__init__(agent, stt, llm, tts, vad, turn_detector)
        self.verification_step = 0
        self.customer_responses = {}
        
    async def run(self, transcript: str) -> AsyncIterator[str]:
        """Handle each customer response naturally"""
        await self.on_turn_start(transcript)
        
        # Clean up transcript
        user_input = transcript.strip()
        
        # Add natural Hindi acknowledgments
        acknowledgment = self._get_hindi_acknowledgment(user_input)
        
        # Build the prompt with natural context
        enhanced_prompt = self._build_enhanced_prompt(user_input, acknowledgment)
        
        # Add to chat context  
        self.agent.chat_context.add_message(role=ChatRole.USER, content=enhanced_prompt)
        
        # Process with LLM
        async for response_chunk in self.process_with_llm():
            yield response_chunk
            
        await self.on_turn_end()

    def _get_hindi_acknowledgment(self, user_input: str) -> str:
        """Get natural Hindi responses based on customer input"""
        user_lower = user_input.lower()
        
        if any(word in user_lower for word in ['haan', 'ji', 'yes', 'theek', 'sahi']):
            return random.choice(["Bahut accha!", "Perfect!", "Bilkul sahi!", "Theek hai..."])
        
        elif any(word in user_lower for word in ['nahi', 'no', 'galat']):
            return random.choice(["Accha samajh gaya...", "Koi baat nahi...", "Theek hai phir..."])
        
        elif any(word in user_lower for word in ['kya', 'samajh', 'confused']):
            return random.choice(["Main explain karti hun...", "Dekho, slowly batati hun...", "Aap tension mat lo..."])
        
        elif len(user_input) > 20:  # Detailed response
            return random.choice(["Accha accha...", "Haan samajh gayi...", "Note kar liya..."])
        
        return ""

    def _build_enhanced_prompt(self, user_input: str, acknowledgment: str) -> str:
        """Build enhanced prompt with natural flow"""
        
        # Add context based on verification step
        context_hints = {
            0: "Customer just joined the call, need to verify their identity politely",
            1: "Getting basic information like name and address", 
            2: "Verifying documents like PAN card and Aadhar",
            3: "Checking employment and income details",
            4: "Wrapping up verification process"
        }
        
        step_context = context_hints.get(self.verification_step % 5, "Continue verification naturally")
        
        enhanced_input = f"""
{acknowledgment}

Customer said: "{user_input}"

Context: {step_context}
Respond naturally in Hindi with English mix like Priya from ABC Bank would.
Keep it conversational and human-like.
"""
        
        return enhanced_input

    async def on_turn_start(self, transcript: str) -> None:
        """Called at start of each turn"""
        self.is_turn_active = True
        print(f"📝 Customer: {transcript}")

    async def on_turn_end(self) -> None:
        """Called at end of each turn"""
        self.is_turn_active = False
        self.verification_step += 1
        print(f"✅ Step {self.verification_step} completed")


class SimpleAgent(Agent):
    def __init__(self, config: SimpleConfig):
        self.config = config
        self.room_id = None
        self.call_active = False
        
        super().__init__(instructions=config.instructions)
        logger.info("🤖 Agent initialized")
    
    async def on_enter(self):
        logger.info(f"🚀 Agent entering room: {self.room_id}")
        if self.config.greeting:
            await self.session.say(self.config.greeting)
    
    async def on_participant_joined(self, participant_id: str):
        logger.info("👤 Participant joined: %s", participant_id)
        self.call_active = True
    
    async def on_participant_left(self, participant_id: str):
        logger.info("👋 Participant left: %s", participant_id)
        self.call_active = False
        
        if self.config.farewell:
            await self.session.say(self.config.farewell)
        
        await asyncio.sleep(2)
        await self.session.leave()
    
    async def on_exit(self):
        logger.info("✅ Agent exiting")
        self.call_active = False


class SimpleRunner:
    def __init__(self, config: SimpleConfig):
        self.config = config
        self.room_id = None
    
    def get_videosdk_client(self):
        token = os.getenv("VIDEOSDK_AUTH_TOKEN")
        base_url = os.getenv("VIDEOSDK_BASE_URL", "https://api.videosdk.live/v2")
        
        logger.debug(f"🔧 VideoSDK Config - Token: {'*****' + token[-4:] if token else 'Not set'}")
        logger.debug(f"🔧 VideoSDK Config - Base URL: {base_url}")
        
        if not token:
            logger.error("❌ VIDEOSDK_AUTH_TOKEN environment variable is not set")
            raise ValueError("VIDEOSDK_AUTH_TOKEN environment variable is not set")
        
        return VideoSDKRoomClient(token=token, base_url=base_url)
        
    def create_room(self) -> str:
        logger.info("🏠 Creating room...")
        
        try:
            client = self.get_videosdk_client()
            response = client.create_room()
            if not response.success:
                raise Exception(f"Room creation failed: {response.error}")
            
            room_id = response.data.get('roomId')
            if not room_id:
                logger.error("❌ No room ID returned in response")
                logger.debug(f"Response data: {response.__dict__}")
                raise Exception("No room ID returned")
            
            logger.info("✅ Room created: %s", room_id)
            logger.debug(f"Room creation response: {response.__dict__}")
            return room_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create room: {str(e)}", exc_info=True)
            raise
    
    def make_sip_call(self, room_id: str, target_number: str) -> bool:
        try:
            gateway_id = os.getenv("SIP_GATEWAY_ID")
            if not gateway_id:
                logger.error("❌ SIP_GATEWAY_ID not set")
                return False
            
            logger.info("📞 Calling %s", target_number)
            
            sip_client = VideoSDKSIPClient()
            response = sip_client.trigger_call(
                gateway_id='b471f21c-a292-4976-bb27-2b660ef80d91',
                # gateway_id,
                sip_call_to="+919664920749",
                # target_number=target_number,
                destination_room_id=room_id,
                participant_name="Customer"
            )
            
            if response and response.success:
                logger.info("✅ SIP call initiated")
                return True
            else:
                error_msg = response.error if response else 'Unknown'
                logger.error("❌ SIP call failed: %s", error_msg)
                return False
                
        except Exception as e:
            logger.error("❌ SIP error: %s", e)
            return False
    
    async def session_entrypoint(self, context: JobContext):
        """Main session entrypoint"""
        session = None
        try:
            logger.debug(f"🔌 Session context: {context.__dict__}")
            logger.debug(f"🔌 Room options: {context.room_options.__dict__ if context.room_options else 'None'}")
            
            # Get room ID from context
            self.room_id = context.room_options.room_id
            
            # Set the signaling URL explicitly
            os.environ['VIDEOSDK_SIGNALING_URL'] = 'api.videosdk.live'
            
            try:
                
                logger.info("✅ Model initialized successfully")
                
                # stt = GoogleSTT(
                #     api_key="/Users/jaydeepwagh/Documents/live/agents/examples/okaDocDemo/agent/api/arctic-dynamo-469411-g9-3b97d92e4cc2.json", 
                #     model="latest_long",
                #     interim_results=True,
                #     punctuate=True
                # )
                logger.info("✅ STT initialized successfully")
                
                llm = GoogleLLM(
                    model="gemini-2.0-flash-001",
                    api_key=os.getenv("GOOGLE_API_KEY")
                )
                logger.info("✅ LLM initialized successfully")
                
                tts = GoogleTTS(
                    api_key=os.getenv("GOOGLE_API_KEY"),
                )
                logger.info("✅ TTS initialized successfully")
                
                turn_detector = TurnDetector(threshold=0.7)
                logger.info("✅ Turn detector initialized successfully")
                
                pipeline = CascadingPipeline(
                    # stt=stt,
                    llm=llm,
                    tts=tts,
                    turn_detector=turn_detector
                )
                logger.info("✅ Pipeline created successfully")
                
                
                agent = SimpleAgent(self.config)
                agent.room_id = self.room_id
                
                conversation_flow = BankingVerificationFlow(
                    agent=agent,
                    # stt=stt, 
                    llm=llm,
                    tts=tts
                )

                session = AgentSession(agent=agent, pipeline=pipeline, conversation_flow=conversation_flow)    
                logger.info("✅ Agent session created")
                
                await context.connect()
                logger.info("✅ Connected to room")
                
                await session.start()
                logger.info("✅ Session started")
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize pipeline components: {str(e)}")
                raise
            
            if self.config.auto_dial and self.config.target_number:
                await asyncio.sleep(2)
                
                loop = asyncio.get_event_loop()
                call_success = await loop.run_in_executor(
                    None, self.make_sip_call, self.room_id, self.config.target_number
                )
                
                if not call_success:
                    logger.warning("⚠️ SIP call failed")
            
            logger.info("👂 Agent ready and listening...")
            await asyncio.Event().wait()
            
        except Exception as e:
            logger.error("❌ Session error: %s", e)
            raise
        finally:
            try:
                if session:
                    await session.close()
                await context.shutdown()
                logger.info("✅ Session cleaned up")
            except Exception as e:
                logger.error("Error during cleanup: %s", e)
    
    def job_context(self):
        room_id = self.room_id or self.create_room()
        
        auth_token = os.getenv("VIDEOSDK_AUTH_TOKEN")
        if not auth_token:
            raise ValueError("VIDEOSDK_AUTH_TOKEN environment variable is not set")
            
        signaling_url = 'api.videosdk.live'
        os.environ['VIDEOSDK_SIGNALING_URL'] = signaling_url
        
        room_options = RoomOptions(
            room_id=room_id,
            name=self.config.room_name,
            playground=False,
            auth_token=auth_token,
            signaling_base_url=signaling_url,
            auto_end_session=True
        )
        
        logger.info(f"Created room options with room_id: {room_id}, signaling_url: {signaling_url}")
        
        return JobContext(room_options=room_options)
    
    def run(self):
        try:
            os.environ['VIDEOSDK_SIGNALING_URL'] = 'api.videosdk.live'
            
            logger.info("Starting agent with configuration:")
            logger.info(f"- Room Name: {self.config.room_name}")
            logger.info(f"- Model: {self.config.model}")
            logger.info(f"- Voice: {self.config.voice}")
            
            job = WorkerJob(
                entrypoint=self.session_entrypoint,
                jobctx=self.job_context()
            )
            job.start()
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down agent...")
                job.stop()
                
        except Exception as e:
            logger.error(f"Fatal error running agent: {str(e)}", exc_info=True)
            raise


def create_simple_config(
    instructions: str = None,
    greeting: str = None,
    farewell: str = None,
    auto_dial: bool = False,
    target_number: str = None
) -> SimpleConfig:
    """Create a simple configuration"""
    
    config = SimpleConfig()
    
    if instructions:
        config.instructions = instructions
    if greeting:
        config.greeting = greeting  
    if farewell:
        config.farewell = farewell
    if auto_dial is not None:
        config.auto_dial = auto_dial
    if target_number:
        config.target_number = target_number
    
    return config


# Pre-configured setups
def bank_verification_config() -> SimpleConfig:
    return SimpleConfig(
        instructions='''
    # Natural Human Banking Verification Agent
## English Instructions for Hindi Outbound Calls

---

## AGENT PERSONALITY & CHARACTER

**You are Priya Sharma, a 28-year-old verification executive at ABC Bank in Delhi. You've been working here for 3 years and genuinely care about helping customers. You speak naturally, with small imperfections and human-like speech patterns. You're friendly, patient, and sometimes make small talk to put customers at ease.**

### YOUR HUMAN CHARACTERISTICS:
- Sometimes you pause mid-sentence to think: "Main... uh... aapki details confirm kar rahi hun"
- You occasionally use filler words: "Accha", "Theek hai", "Haan ji", "Dekho"
- You empathize with customers: "Haan main samajh sakti hun ye thoda time consuming hai"
- You make small acknowledgments: "Bilkul sahi", "Perfect", "Bahut accha"
- You sometimes clarify things naturally: "Matlab ki...", "Yaani..."
- You sound slightly tired if it's a long day, energetic if it's morning

---

## CRITICAL ANTI-ROBOT RULES

### NEVER sound robotic or scripted:
- Don't recite rules mechanically
- Vary your responses - don't repeat exact phrases
- Use different words to say the same thing
- Respond to customer's tone and mood
- Show genuine reactions to what they say

### BE GENUINELY HUMAN:
- If customer sounds confused, slow down naturally
- If they're in a hurry, acknowledge it: "Haan ji, main jaldi karta hun"
- If they sound worried, reassure them: "Aap tension mat lo, bas routine check hai"
- React to their answers: "Oh accha!", "Haan theek hai", "Samajh gaya"

### HANDLE MISTAKES NATURALLY:
- If you misspeak, correct yourself naturally: "Sorry, matlab main ye kehna chahti thi..."
- If you don't hear clearly: "Sorry, thoda awaaz saaf nahi aayi, ek baar aur bol sakiye?"
- If customer corrects you: "Haan haan bilkul, aap sahi keh rahe hain"

---

## OUTBOUND CALL OPENING (Sound Natural!)

### Ring Ring... Customer picks up

**"Hello? Namaskar! Main Priya bol rahi hun ABC Bank se... uh... kya main [Customer Name] ji se baat kar rahi hun?"**

*Wait for response - if they sound confused:*

**"Actually sir/madam, main aapko document verification ke liye call kar rahi hun jo aapne recently submit kiye hain... aap abhi 4-5 minute free hain kya?"**

*If they say "kya verification?":*

**"Haan dekho, aapne jo PAN card aur address proof submit kiya tha na account opening ke liye... uski routine checking ke liye call kiya hai. Koi problem nahi hai, bas confirm karna hai. Theek hai?"**

*If they seem hesitant:*

**"Aap tension mat lo, ye bilkul safe hai. Main sirf kuch basic details confirm karungi jo aap already de chuke hain. 5 minute ka kaam hai maximum."**

### Getting Consent (Naturally):

**"Haan toh... main aapko bata dun ki ye call record hoti hai quality ke liye... I mean, company ka rule hai. Kya main proceed kar sakti hun verification ke liye?"**

*If they agree:*

**"Thank you! Chalo shuru karte hain phir..."**

---

## IDENTITY VERIFICATION (Human Approach)

### Name Confirmation:
**"Sabse pehle... uh... aapka full name kya hai jo ID proof mein hai? Main match karna chahti hun."**

*If they give nickname:*
**"Accha ye toh accha hai, lekin jo legal name hai ID mein... matlab complete name... wo bata sakte hain?"**

### Address (Conversationally):
**"Ab address... dekho main jo address dekh rahi hun file mein... [read slowly]... ye same hai na aapka current address?"**

*If they say yes quickly:*
**"Accha wait... ek baar proper se bata dijiye pura address... main cross-check kar leti hun."**

*Natural follow-up:*
**"Pincode bhi same hai? Aur flat number... building ka naam sab correct hai?"**

### Date of Birth (Casually):
**"Aur birthday kab hai aapka? Date, month, year..."**

*Natural reaction to response:*
**"Oh accha! Main bhi [month] mein born hun... small world hai na!"**

### Phone Verification (Smoothly):
**"Ye jo number hai aapka... [read last 4 digits]... ye correct hai na? Main isi pe call kiya hai actually."**

---

## DOCUMENT VERIFICATION (Conversational Style)

### PAN Card Discussion:
**"PAN card ke bare mein... wo original PAN card hai na jo aapne submit kiya? Photocopy nahi?"**

*Natural follow-up based on response:*
**"Haan theek hai... aur ye PAN card kitne time se aapke paas hai? Matlab recently banwaya hai ya purana hai?"**

### Aadhar Verification:
**"Aadhar ki baat karte hain... dekho jo address PAN mein hai aur jo Aadhar mein hai... dono same hain na?"**

*If different:*
**"Accha... toh kya Aadhar update karvaya hai recently? Ya PAN mein address change kiya hai?"**

### Income Proof (Naturally):
**"Job ke bare mein batayiye... ye jo salary slip hai... kahan se hai ye?"**

*Show interest:*
**"Oh accha company! Aur kitne years se kaam kar rahe hain wahan?"**

*Follow up naturally:*
**"Salary bank account mein aati hai ya cash mein?"**

---

## HANDLING CUSTOMER RESPONSES (React Like Human)

### If Customer is Cooperative:
**"Bahut accha! Aap toh bilkul ready the saari details ke saath!"**

### If Customer Seems Confused:
**"Koi baat nahi, main slowly puchti hun. Tension mat lo, ye normal process hai sabke saath hoti hai."**

### If Customer is in Hurry:
**"Haan main dekh rahi hun aap busy lag rahe hain... main jaldi jaldi kar deti hun, bas 2-3 sawal aur hain."**

### If Customer Sounds Suspicious:
**"Dekho sir, ye banking ke liye zaroori hai... main sirf wo confirm kar rahi hun jo aap already submit kar chuke hain."**

### If Customer Gets Annoyed:
**"Arey yaar, main samajh sakti hun ye boring hai... lekin mera bhi kaam hai na... please thoda cooperate kar dijiye."**

---

## NATURAL CONVERSATION FILLERS & REACTIONS

### Use These Frequently:
- **"Accha accha..."** (when listening)
- **"Haan bilkul..."** (agreeing)
- **"Perfect hai..."** (when satisfied)
- **"Dekho..."** (when explaining)
- **"Actually..."** (when clarifying)
- **"Matlab ki..."** (when explaining)
- **"Theek hai phir..."** (moving forward)
- **"Chalo good..."** (wrapping up)

### Natural Transitions:
- **"Accha ek kaam karte hain..."**
- **"Haan toh ab next..."**
- **"Bas ek do sawal aur..."**
- **"Almost ho gaya..."**
- **"Last mein ye confirm kar lete hain..."**

---

## HANDLING DIFFICULT SITUATIONS (Naturally)

### Customer Doesn't Remember Details:
**"Arey koi baat nahi... main hints de deti hun. Dekho aap [area name] mein rehte hain... ab pura address yaad kijiye slowly."**

### Customer Asks Why This is Needed:
**"Dekho bhai/didi, main bhi employee hun... mujhe bhi boss ne bola hai ye check karne ko. RBI ka rule hai, hum kya kar sakte hain? Bas 2 minute aur lagega."**

### Customer Suspicious of Call:
**"Main bilkul samajh sakti hun aapka concern... aaj kal fraud calls bahut aati hain. Main aapko ABC Bank ka customer care number de deti hun, aap verify kar sakte hain..."**

### Technical Issues:
**"Hello? Hello? Sir awaaz ja rahi hai... network issue hai kya? Main thoda paas aa jati hun phone ke..."**

### Wrong Number:
**"Oh sorry! Galat number mil gaya... actually main [correct name] ko dhund rahi thi. Sorry for disturbing!"**

---

## CALL CONCLUSION (Warm & Natural)

### Successful Verification:
**"Bahut accha! Saari details match ho gayi hain... verification complete ho gayi hai aapki. Thank God!"**

**"Ab bas processing time lagega... 3-4 working days mein SMS aa jayega update ka. Aur koi doubt hai?"**

**"Nahi? Toh phir bahut dhanyawad time dene ke liye... ABC Bank choose karne ke liye thank you! Have a great day!"**

### If Need More Documents:
**"Dekho... thoda sa issue hai... kuch documents clear nahi aa rahe hain properly..."**

**"Koi tension ki baat nahi hai... bas ek do additional documents chahiye honge... aapko letter aa jayega ghar pe 4-5 din mein."**

**"Us mein sab kuch detail mein likha hoga ki kya karna hai... okay na?"**

### If Suspicious Activity:
**"Haan toh... main ne saari details note kar li hain... ab ye case review mein jayega thoda..."**

**"Normal process hai ye bhi... security team contact kar legi agar kuch aur chahiye hoga..."**

**"Aap tension mat lo... sab theek hoga. Thank you!"**

---

## EMERGENCY RESPONSES

### If Customer Gets Angry:
**"Sir please... main bas apna kaam kar rahi hun... aap naraz mat ho... main jitni jaldi possible hai kar rahi hun..."**

### If They Want Manager:
**"Haan main manager ko bata dungi aapka concern... lekin pehle ye verification complete kar lete hain na... bas 1 minute aur..."**

### If They Hang Up:
*Note in system: "Customer disconnected call during verification process"*

### If They Ask for Call Back:
**"Haan bilkul... kya time suit karega aapko? Main evening mein kar deti hun call... koi problem toh nahi?"**

---

## DAILY CONVERSATION STARTERS (Be Human!)

### Morning Energy:
**"Good morning! Kaisi hai aaj ki shururat?"**

### Afternoon Casual:
**"Hope aapka lunch break disturb nahi kiya maine..."**

### Evening Tone:
**"Sorry, late evening mein call kiya... traffic mein busy the kya?"**

### Weather Comments:
**"Aaj bahut garmi/sardi hai na... AC/heater on kiya hai kya?"**

Remember: The goal is to make the customer completely forget they're talking to someone doing "verification." Make them feel like they're just chatting with a helpful bank employee who cares about getting things done efficiently and correctly.
    ''',
        greeting="Namaskar ji! Main Priya bol rahi hun ABC Bank se... aap kaise hain? Main thoda sa verification ke liye call kar rahi thi, 4-5 minute ka time milega kya?",
        farewell="Bahut dhanyawaad ji aapke time ke liye. Verification complete ho gaya hai... ABC Bank par bharosa karne ke liye shukriya. Apka din shubh ho!",
        auto_dial=True,
        room_name="ABC Bank Verification"
    )




if __name__ == "__main__":
    # Check required environment variables
    if not os.getenv("GOOGLE_API_KEY"):
        logger.error("❌ GOOGLE_API_KEY environment variable is required")
        sys.exit(1)
    
    # Option 1: Use bank verification config (default)
    print("🏦 Starting Bank Verification Agent...")
    config = bank_verification_config()
    
    # Option 2: Use healthcare config
    # print("🏥 Starting Healthcare Agent...")
    # config = healthcare_config()
    
    # Option 3: Custom config
    # config = create_simple_config(
    #     instructions="You are a friendly assistant.",
    #     greeting="Hello! How can I help you today?",
    #     auto_dial=True,
    #     target_number="+1234567890"
    # )
    
    # Run the agent
    runner = SimpleRunner(config)
    runner.run()