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

env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
load_dotenv(dotenv_path=env_path)

project_root = Path(__file__).resolve().parent.parent.parent.parent  # Go up to verificationDemo
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

if str(project_root.parent) not in sys.path:
    sys.path.insert(0, str(project_root.parent))

from videosdk.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerJob,
    RoomOptions,
    CascadingPipeline,
)
from videosdk.plugins.google import (
    GoogleLLM,
    GoogleTTS, 
)
from videosdk.plugins.sarvamai import SarvamAISTT
from videosdk.plugins.turn_detector import TurnDetector
from examples.verificationDemo.api.room_api import VideoSDKRoomClient
from examples.verificationDemo.api.sip_api import VideoSDKSIPClient
from examples.verificationDemo.core.conversation_flow.banking_verification_flow import BankingVerificationFlow
from examples.verificationDemo.core.conversation_flow.class_plus_conversation_flow import ClassPlusConversationFlow
from examples.verificationDemo.core.cascading.custom_agents.bank_verification_agent.bank_verification_agent import (
    BankVerificationAgent,
    BankVerificationConfig,
    bank_verification_config
)
from examples.verificationDemo.core.cascading.custom_agents.class_plus_sales_agent.class_plus_sales_agent import create_classplus_agent

class SimpleRunner:
    def __init__(self, config: BankVerificationConfig):
        self.config = config
        self.room_id = None
    
    def create_room(self) -> str:
        try:
            token = os.getenv("VIDEOSDK_AUTH_TOKEN")
            if not token:
                raise ValueError("VIDEOSDK_AUTH_TOKEN environment variable is not set")
            
            base_url = os.getenv("VIDEOSDK_BASE_URL", "https://api.videosdk.live/v2")
            if not base_url:
                raise ValueError("VIDEOSDK_BASE_URL environment variable is not set")

            client = VideoSDKRoomClient(token=token, base_url=base_url)
            response = client.create_room()
            if not response.success:
                raise Exception(f"Room creation failed: {response.error}")
            
            room_id = response.data.get('roomId')
            if not room_id:
                raise Exception("No room ID returned")
            
            return room_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create room: {str(e)}", exc_info=True)
            raise
    
    def make_sip_call(self, room_id: str, target_number: str) -> bool:
        try:
            gateway_id = os.getenv("SIP_GATEWAY_ID")
            if not gateway_id:
                raise ValueError("SIP_GATEWAY_ID environment variable is not set")
            
            sip_client = VideoSDKSIPClient()
            if not sip_client:
                raise ValueError("SIP client not initialized")
            
            response = sip_client.trigger_call(
                gateway_id=gateway_id,
                sip_call_to=target_number,
                destination_room_id=room_id,
                participant_name="Customer"
            )
            
            if response and response.success:
                return True
            else:
                error_msg = response.error if response else 'Unknown'
                raise ValueError("SIP call failed: %s", error_msg)
                
        except Exception as e:
            raise ValueError("SIP error: %s", e)
    
    async def session_entrypoint(self, context: JobContext):
        session = None
        try:
            self.room_id = context.room_options.room_id
            os.environ['VIDEOSDK_SIGNALING_URL'] = 'api.videosdk.live'
            
            try:
                
                logger.info("✅ Model initialized successfully")
                
                stt = SarvamAISTT(
                    api_key=os.getenv("SARVAMAI_API_KEY"),
                    model="saarika:v2",
                    language="en-IN"
                ) 
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
                    stt=stt,
                    llm=llm,
                    tts=tts,
                    turn_detector=turn_detector
                )
                logger.info("✅ Pipeline created successfully")
                
                # Original Bank Verification Flow (commented out)
                # agent = BankVerificationAgent(self.config)
                # agent.room_id = self.room_id
                # conversation_flow = BankingVerificationFlow(
                #     agent=agent,
                #     stt=stt, 
                #     llm=llm,
                #     tts=tts
                # )

                # New ClassPlus Sales Flow
                classplus_agent = create_classplus_agent(
                    target_number="9664920749",
                    language="en-US",
                )
                classplus_agent.room_id = self.room_id
                
                conversation_flow = ClassPlusConversationFlow(
                    agent=classplus_agent,
                    stt=stt,
                    llm=llm,
                    tts=tts
                )

                
                session = AgentSession(
                    agent=classplus_agent, 
                    pipeline=pipeline, 
                    conversation_flow=conversation_flow
                )
                
                
                
                await context.connect()
                await session.start()
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize pipeline components: {str(e)}")
                # SIP call functionality temporarily disabled for testing
                # if self.config.auto_dial and self.config.target_number:
                #     logger.info(f"📞 Auto-dialing {self.config.target_number}")
                #     
                #     loop = asyncio.get_event_loop()
                #     call_success = await loop.run_in_executor(
                #         None, self.make_sip_call, self.room_id, self.config.target_number
                #     )
                #     
                #     if not call_success:
                #         logger.warning("⚠️ SIP call failed")
            
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
            playground=True,  # Changed to True for testing
            auth_token=auth_token,
            signaling_base_url=signaling_url,
            auto_end_session=True
        )
        
        logger.info(f"Created room options with room_id: {room_id}, signaling_url: {signaling_url}")
        
        return JobContext(room_options=room_options)
    
    def run(self):
        try:
            os.environ['VIDEOSDK_SIGNALING_URL'] = 'api.videosdk.live'  
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


if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        sys.exit(1)
    
    config = bank_verification_config()
    
    runner = SimpleRunner(config)
    runner.run()