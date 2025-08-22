import asyncio
import os
import sys
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from videosdk.agents import Agent, AgentSession, RealTimePipeline, JobContext, RoomOptions
from videosdk.plugins.google import GeminiRealtime, GeminiLiveConfig
from typing import Dict

# Load environment variables
load_dotenv()

# Configuration
VIDEOSDK_TOKEN = os.getenv('VIDEOSDK_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Call configuration
TARGET_PHONE_NUMBER = "+919664920749"
GATEWAY_ID = "9908f984-fd53-433d-b192-3895e6a2d3e0"
CALLER_ID = "+919664920749"

# Agent configurations (same as before)
AGENT_CONFIG = {
    'verification': {
        'name': 'Verification Agent',
        'voice': 'Puck',
        'instructions': 'You are a professional verification agent. Speak clearly and verify user information.',
        'greeting': 'Hello! This is an automated verification call.',
        'farewell': 'Thank you for your time. Have a great day!',
        'conversation_flow': {
            'greeting': {
                'message': 'Could you please confirm your full name?',
                'next': 'confirm_identity'
            },
            'confirm_identity': {
                'message': 'Thank you. Could you provide your date of birth?',
                'next': 'verify_dob'
            },
            'verify_dob': {
                'message': 'Could you confirm your current address?',
                'next': 'verify_address'
            },
            'verify_address': {
                'message': 'Perfect! Your information has been verified. Thank you!',
                'next': None
            }
        }
    },
    'medical_feedback': {
        'name': 'Medical Feedback Agent',
        'voice': 'Aoede',
        'instructions': 'You are a friendly medical feedback agent.',
        'greeting': 'Hello! This is a feedback call about your recent medical visit.',
        'farewell': 'Thank you for your valuable feedback!',
        'conversation_flow': {
            'greeting': {
                'message': 'Could you confirm you had a recent visit with us?',
                'next': 'confirm_visit'
            },
            'confirm_visit': {
                'message': 'On a scale of 1 to 5, how would you rate your experience?',
                'next': 'rate_experience'
            },
            'rate_experience': {
                'message': 'How would you rate our service quality, from 1 to 5?',
                'next': 'service_quality'
            },
            'service_quality': {
                'message': 'Any suggestions for improvement?',
                'next': 'improvement'
            },
            'improvement': {
                'message': 'Thank you for your feedback!',
                'next': None
            }
        }
    }
}

class VideoSDKCallTrigger:
    """Handles triggering outbound SIP calls via VideoSDK API"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.videosdk.live"
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
    
    def create_room(self, room_id: str = None) -> Dict:
        """Create a VideoSDK room"""
        try:
            url = f"{self.base_url}/v2/rooms"
            data = {}
            if room_id:
                data["roomId"] = room_id
                
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            
            room_data = response.json()
            print(f"✅ Room created: {room_data['roomId']}")
            return room_data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to create room: {str(e)}")
            raise
    
    def trigger_sip_call(self, room_id: str, phone_number: str, caller_id: str, gateway_id: str) -> Dict:
        """Trigger an outbound SIP call using VideoSDK API"""
        try:
            url = f"{self.base_url}/v2/sip/call"

            payload = {
                "gatewayId": gateway_id,
                "sipCallTo": phone_number,
                "destinationRoomId": room_id,
                "participant": {"name": "Outbound Agent"}
            }

            print(f"📞 Triggering call to {phone_number}")
            print(f"🏠 Room ID: {room_id}")

            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()

            call_data = response.json()
            print(f"🎉 Call triggered successfully!")
            print(f"📞 Call ID: {call_data.get('id', 'N/A')}")
            return call_data

        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to trigger call: {str(e)}")
            if hasattr(e.response, 'text'):
                print(f"Error details: {e.response.text}")
            raise


class SimpleOutboundAgent(Agent):
    """Simplified outbound calling agent that works with VideoSDK"""
    
    def __init__(self, agent_type: str = 'verification'):
        self.agent_type = agent_type
        self.config = AGENT_CONFIG[agent_type]
        self.conversation_flow = self.config['conversation_flow']
        self.current_context = None
        self.conversation_history = []
        
        super().__init__(
            instructions=self.config['instructions'],
            tools=[]
        )
    
    async def on_enter(self) -> None:
        """Called when the agent joins the room"""
        print(f"🤖 {self.config['name']} joined the room")
        await self.session.say(self.config['greeting'])
    
    async def on_exit(self) -> None:
        """Called when the agent leaves the room"""
        await self.session.say(self.config['farewell'])
        print("🤖 Agent left the room")
    
    async def on_participant_join(self, participant) -> None:
        """Called when a participant (caller) joins"""
        print(f"📞 Caller joined: {participant.get('name', 'Unknown')}")
        
        # Initialize conversation context
        self.current_context = {
            'current_step': 'greeting',
            'responses': {},
            'completed_steps': set(),
            'start_time': datetime.now().isoformat()
        }
        
        # Wait for connection to stabilize, then start
        await asyncio.sleep(3)
        await self.start_conversation()
    
    async def start_conversation(self):
        """Start the conversation flow"""
        greeting_step = self.conversation_flow['greeting']
        await self.session.say(greeting_step['message'])
        print(f"🗣️  Agent: {greeting_step['message']}")
        self.current_context['current_step'] = greeting_step['next']
    
    async def on_speech_end(self, text: str) -> None:
        """Handle user speech input"""
        print(f"👤 Caller: {text}")
        
        if not self.current_context:
            return
        
        # Store the response
        current_step = self.current_context['current_step']
        self.current_context['responses'][current_step] = text
        self.current_context['completed_steps'].add(current_step)
        
        # Record in history
        self.conversation_history.append({
            'timestamp': datetime.now().isoformat(),
            'role': 'user',
            'content': text,
            'step': current_step
        })
        
        # Process and continue
        await self.handle_response(text)
    
    async def handle_response(self, response: str):
        """Process response and continue conversation"""
        current_step = self.current_context['current_step']
        
        # Get next step from conversation flow
        if current_step in self.conversation_flow:
            step_config = self.conversation_flow[current_step]
            next_step = step_config['next']
            
            if next_step and next_step in self.conversation_flow:
                # Continue to next step
                next_step_config = self.conversation_flow[next_step]
                self.current_context['current_step'] = next_step
                
                await asyncio.sleep(1.5)  # Natural pause
                await self.session.say(next_step_config['message'])
                print(f"🗣️  Agent: {next_step_config['message']}")
            else:
                # Conversation complete
                await self.end_conversation()
    
    async def end_conversation(self):
        """End the conversation"""
        print("✅ Conversation completed!")
        await self.generate_summary()
        
        # End politely and leave
        await asyncio.sleep(2)
        await self.session.say(self.config['farewell'])
        await asyncio.sleep(1)
        await self.session.leave()
    
    async def generate_summary(self):
        """Generate conversation summary"""
        if not self.current_context:
            return
        
        summary = {
            'agent_type': self.agent_type,
            'start_time': self.current_context['start_time'],
            'end_time': datetime.now().isoformat(),
            'steps_completed': len(self.current_context['completed_steps']),
            'responses': self.current_context['responses'],
            'conversation_history': self.conversation_history
        }
        
        # Add specific analytics
        if self.agent_type == 'medical_feedback':
            ratings = []
            for response in self.current_context['responses'].values():
                for char in str(response):
                    if char.isdigit() and 1 <= int(char) <= 5:
                        ratings.append(int(char))
                        break
            
            summary['ratings'] = ratings
            summary['average_rating'] = sum(ratings) / len(ratings) if ratings else None
        
        print("\n📋 CALL SUMMARY:")
        print("=" * 50)
        print(json.dumps(summary, indent=2))
        print("=" * 50)


async def create_voice_pipeline() -> RealTimePipeline:
    """Create the voice pipeline for the agent.

    This function will:
     - create the GeminiRealtime model
     - if a running asyncio loop exists, assign it to model.loop so audio playback can be used
     - if no running loop exists, fall back to TEXT-only modality (avoids runtime error)
    """
    # create the model with desired config (AUDIO intended)
    desired_modalities = ["AUDIO"]
    model = GeminiRealtime(
        model="gemini-2.0-flash-live-001",
        api_key=GOOGLE_API_KEY,
        config=GeminiLiveConfig(
            voice="Puck",
            response_modalities=desired_modalities
        )
    )

    # If there's a running loop, attach it to the model so audio playback is possible.
    try:
        running_loop = asyncio.get_running_loop()
        # only set loop if we actually have one
        if running_loop:
            model.loop = running_loop
            # ensure AUDIO stays enabled
            if "AUDIO" not in model.config.response_modalities:
                model.config.response_modalities.append("AUDIO")
            print("ℹ️ Running asyncio loop detected — audio enabled on Gemini model.")
    except RuntimeError:
        # No running loop — fallback: remove AUDIO to avoid requiring an event loop
        if "AUDIO" in model.config.response_modalities:
            model.config.response_modalities = [m for m in model.config.response_modalities if m != "AUDIO"]
        print("⚠️ No running asyncio loop detected — falling back to TEXT-only mode to avoid audio errors.")

    return RealTimePipeline(model=model)


# --- Helper to safely await things that might or might not be coroutines ---
async def _maybe_await(maybe_coro):
    if maybe_coro is None:
        return None
    if asyncio.iscoroutine(maybe_coro):
        return await maybe_coro
    return maybe_coro


async def setup_agent_and_trigger_call(agent_type: str = 'verification'):
    """Set up agent in room and trigger the outbound call (robust for different SDK versions)."""
    
    print(f"🚀 Starting Outbound Call System")
    print(f"📞 Target: {TARGET_PHONE_NUMBER}")
    print(f"🤖 Agent: {agent_type}")
    print("=" * 60)
    
    call_trigger = VideoSDKCallTrigger(VIDEOSDK_TOKEN)
    session = None
    context = None
    
    try:
        # Step 1: Create room
        room_id = f"outbound_{agent_type}_{int(datetime.now().timestamp())}"
        room_data = call_trigger.create_room(room_id)
        room_id = room_data['roomId']
        
        # Step 2: Create agent + pipeline
        agent = SimpleOutboundAgent(agent_type)
        pipeline = await create_voice_pipeline()

        # Step 3: Set up room and context
        room_options = RoomOptions(
            room_id=room_id,
            auth_token=VIDEOSDK_TOKEN,
            name=f"Outbound Agent - {agent_type.title()}",
            playground=False
        )
        context = JobContext(room_options=room_options)

        # STEP 3.5: Create session — try newer SDK style first, then fallback
        try:
            # Newer SDKs accept ctx=context
            session = AgentSession(ctx=context, agent=agent, pipeline=pipeline)
            print("ℹ️ AgentSession created with ctx (newer SDK).")
        except TypeError:
            # Older SDKs: only (agent, pipeline)
            session = AgentSession(agent=agent, pipeline=pipeline)
            print("ℹ️ AgentSession created without ctx (older SDK).")
        
        # Step 4: Connect context first
        print(f"🔗 Connecting context / room...")
        await _maybe_await(context.connect())

        # If the context has an API to attach/add a session, try that (older SDKs)
        if hasattr(context, "add_session"):
            try:
                context.add_session(session)
                print("ℹ️ Session attached to context via add_session().")
            except Exception as e:
                print(f"⚠️ context.add_session() failed: {e}")
        elif hasattr(context, "register_session"):
            try:
                context.register_session(session)
                print("ℹ️ Session attached to context via register_session().")
            except Exception as e:
                print(f"⚠️ context.register_session() failed: {e}")
        else:
            # no-op, many newer SDKs do not require manual attach
            print("ℹ️ No explicit session-attach method found on JobContext; continuing.")

        # Start session
        print(f"▶️ Starting agent session...")
        await _maybe_await(session.start())
        print(f"✅ Agent is live in room: {room_id}")
        
        # Step 5: Trigger call after giving agent a moment
        await asyncio.sleep(5)
        print(f"📞 Triggering call to {TARGET_PHONE_NUMBER}...")
        call_data = call_trigger.trigger_sip_call(
            room_id=room_id,
            phone_number=TARGET_PHONE_NUMBER,
            caller_id=CALLER_ID,
            gateway_id=GATEWAY_ID
        )
        
        print(f"🎉 CALL INITIATED! Call ID: {call_data.get('callId')}")
        print(f"⏱️  Call connecting...")
        
        # Step 6: Keep running
        print("\n⏳ Call in progress... (Press Ctrl+C to stop)")
        try:
            await asyncio.sleep(600)
        except KeyboardInterrupt:
            print("\n🛑 Stopping...")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise
    finally:
        # Clean shutdown, defensive
        try:
            if session:
                await _maybe_await(session.close())
        except Exception as e:
            print(f"⚠️ session.close() error: {e}")
        try:
            if context:
                await _maybe_await(context.shutdown())
        except Exception as e:
            print(f"⚠️ context.shutdown() error: {e}")


def main():
    """Main function"""
    
    # Check environment variables
    if not VIDEOSDK_TOKEN or not GOOGLE_API_KEY:
        print("❌ Missing environment variables:")
        print("   - VIDEOSDK_TOKEN")
        print("   - GOOGLE_API_KEY")
        return
    
    # Check gateway and caller ID
    if GATEWAY_ID == "your_gateway_id" or CALLER_ID == "+your_caller_id":
        print("❌ Please update GATEWAY_ID and CALLER_ID in the code")
        print("   - GATEWAY_ID: Your VideoSDK gateway ID")
        print("   - CALLER_ID: Your outbound caller ID number")
        return
    
    # Get agent type
    agent_type = sys.argv[1] if len(sys.argv) > 1 else 'verification'
    if agent_type not in ['verification', 'medical_feedback']:
        print("❌ Invalid agent type. Use: verification or medical_feedback")
        return
    
    print("🔧 Configuration validated!")
    print(f"📞 Target: {TARGET_PHONE_NUMBER}")
    print(f"🤖 Agent: {agent_type}")
    print(f"🏗️  Gateway: {GATEWAY_ID}")
    
    # Confirm before proceeding
    confirm = input(f"\n⚠️  Make REAL call to {TARGET_PHONE_NUMBER}? (y/N): ")
    if confirm.lower() not in ['y', 'yes']:
        print("❌ Cancelled")
        return
    
    try:
        # Ensure we have an event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the async function
        loop.run_until_complete(setup_agent_and_trigger_call(agent_type))
    except KeyboardInterrupt:
        print("\n👋 Stopped")
    except Exception as e:
        print(f"❌ Failed: {str(e)}")


if __name__ == "__main__":
    main()