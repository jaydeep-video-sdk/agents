#!/usr/bin/env python3
import asyncio
import os
import sys
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional

# VideoSDK
from videosdk.agents import Agent, AgentSession, RealTimePipeline, JobContext, RoomOptions
from videosdk.plugins.google import GeminiRealtime, GeminiLiveConfig

# =========================
# ENV & CONSTANTS
# =========================
load_dotenv()

VIDEOSDK_TOKEN = os.getenv("VIDEOSDK_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

TARGET_PHONE_NUMBER = "+919664920749"
GATEWAY_ID = "9908f984-fd53-433d-b192-3895e6a2d3e0"
CALLER_ID = "+919664920749"  # outbound caller id (must be verified/allowed on your SIP gateway)

# =========================
# AGENT CONFIGS
# =========================
AGENT_CONFIG = {
    "verification": {
        "name": "Verification Agent",
        "voice": "Puck",
        "instructions": (
            "You are a professional verification agent. Speak clearly and verify user information. "
            "Keep responses short and wait for the caller to finish speaking before the next question."
        ),
        "greeting": "Hello! This is an automated verification call.",
        "farewell": "Thank you for your time. Have a great day!",
        "conversation_flow": {
            "greeting": {"message": "Could you please confirm your full name?", "next": "confirm_identity"},
            "confirm_identity": {"message": "Thank you. Could you provide your date of birth?", "next": "verify_dob"},
            "verify_dob": {"message": "Could you confirm your current address?", "next": "verify_address"},
            "verify_address": {"message": "Perfect! Your information has been verified. Thank you!", "next": None},
        },
    },
    "medical_feedback": {
        "name": "Medical Feedback Agent",
        "voice": "Aoede",
        "instructions": "You are a friendly medical feedback agent.",
        "greeting": "Hello! This is a feedback call about your recent medical visit.",
        "farewell": "Thank you for your valuable feedback!",
        "conversation_flow": {
            "greeting": {"message": "Could you confirm you had a recent visit with us?", "next": "confirm_visit"},
            "confirm_visit": {"message": "On a scale of 1 to 5, how would you rate your experience?", "next": "rate_experience"},
            "rate_experience": {"message": "How would you rate our service quality, from 1 to 5?", "next": "service_quality"},
            "service_quality": {"message": "Any suggestions for improvement?", "next": "improvement"},
            "improvement": {"message": "Thank you for your feedback!", "next": None},
        },
    },
}

# =========================
# HELPERS
# =========================
async def _maybe_await(maybe_coro):
    if maybe_coro is None:
        return None
    if asyncio.iscoroutine(maybe_coro):
        return await maybe_coro
    return maybe_coro

def _now():
    return datetime.now().isoformat(timespec="seconds")

# =========================
# VIDEOSDK REST CALLER
# =========================
class VideoSDKCallTrigger:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.videosdk.live"
        self.headers = {"Authorization": token, "Content-Type": "application/json"}

    def create_room(self, room_id: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/v2/rooms"
        data = {"roomId": room_id} if room_id else {}
        resp = requests.post(url, headers=self.headers, json=data, timeout=20)
        resp.raise_for_status()
        room_data = resp.json()
        print(f"✅ Room created: {room_data.get('roomId')}")
        return room_data

    def trigger_sip_call(self, room_id: str, phone_number: str, caller_id: str, gateway_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/v2/sip/call"
        payload = {
            "gatewayId": gateway_id,
            "sipCallTo": phone_number,
            "callerId": caller_id,
            "destinationRoomId": room_id,
            "participant": {"name": "Outbound Agent"},
        }
        print(f"📞 Triggering call to {phone_number} (Room: {room_id})")
        resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json() if resp.text else {}
        print(f"🎉 Call triggered successfully! Call ID: {data.get('id', 'N/A')}")
        return data

# =========================
# SIMPLE OUTBOUND AGENT
# =========================
class SimpleOutboundAgent(Agent):
    def __init__(self, agent_type: str = "verification"):
        self.agent_type = agent_type
        self.config = AGENT_CONFIG[agent_type]
        self.conversation_flow = self.config["conversation_flow"]
        self.current_context = None
        self.conversation_history: List[Dict[str, Any]] = []
        super().__init__(instructions=self.config["instructions"], tools=[])

    async def on_enter(self) -> None:
        print(f"🤖 {self.config['name']} joined the room @ {_now()}")
        await asyncio.sleep(0.8)
        try:
            await self.session.say(self.config["greeting"])
        except Exception as e:
            print(f"❌ say(greeting) failed: {e}")
        self.current_context = {
            "current_step": "greeting",
            "responses": {},
            "completed_steps": set(),
            "start_time": _now(),
        }

    async def on_exit(self) -> None:
        try:
            await self.session.say(self.config["farewell"])
        except Exception as e:
            print(f"❌ say(farewell) failed: {e}")
        print("🤖 Agent left the room")

    async def on_participant_join(self, participant) -> None:
        name = participant.get("name", "Unknown")
        print(f"📞 Participant joined: {name} @ {_now()}")
        if not self.current_context:
            self.current_context = {
                "current_step": "greeting",
                "responses": {},
                "completed_steps": set(),
                "start_time": _now(),
            }
        await asyncio.sleep(2.0)
        if self.current_context["current_step"] == "greeting":
            await self.start_conversation()

    async def on_participant_leave(self, participant) -> None:
        name = participant.get("name", "Unknown")
        print(f"📴 Participant left: {name} @ {_now()}")
        if self.current_context:
            await self.end_conversation()

    async def start_conversation(self):
        step = self.conversation_flow["greeting"]
        try:
            await self.session.say(step["message"])
            print(f"🗣️ Agent: {step['message']}")
        except Exception as e:
            print(f"❌ say(step:greeting) failed: {e}")
        self.current_context["current_step"] = step["next"]

    async def on_speech_end(self, text: str) -> None:
        print(f"👤 Caller: {text}")
        if not self.current_context:
            return
        current_step = self.current_context["current_step"]
        self.current_context["responses"][current_step] = text
        self.current_context["completed_steps"].add(current_step)
        self.conversation_history.append(
            {"timestamp": _now(), "role": "user", "content": text, "step": current_step}
        )
        await self.handle_response(text)

    async def handle_response(self, _: str):
        if not self.current_context:
            return
        current_step = self.current_context["current_step"]
        if current_step in self.conversation_flow:
            next_step = self.conversation_flow[current_step].get("next")
            if next_step and next_step in self.conversation_flow:
                self.current_context["current_step"] = next_step
                msg = self.conversation_flow[next_step]["message"]
                await asyncio.sleep(1.2)
                try:
                    await self.session.say(msg)
                    print(f"🗣️ Agent: {msg}")
                except Exception as e:
                    print(f"❌ say(next_step) failed: {e}")
            else:
                await self.end_conversation()

    async def end_conversation(self):
        if not self.current_context:
            return
        await asyncio.sleep(0.8)
        try:
            await self.session.say(self.config["farewell"])
        except Exception as e:
            print(f"❌ say(farewell) failed: {e}")
        await asyncio.sleep(1.2)
        try:
            await self.session.leave()
        except Exception as e:
            print(f"⚠️ leave() failed: {e}")
        self.current_context = None

# =========================
# PIPELINE (GEMINI LIVE)
# =========================
async def create_voice_pipeline(voice: str) -> RealTimePipeline:
    print("🔧 Creating Gemini Realtime pipeline…")
    model = GeminiRealtime(
        model="gemini-2.0-flash-live-001",
        api_key=GOOGLE_API_KEY,
        config=GeminiLiveConfig(
            voice=voice,
            response_modalities=["AUDIO"],
        ),
    )
    try:
        model.loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        model.loop = loop

    pipeline = RealTimePipeline(model=model)
    if hasattr(pipeline, "start"):
        try:
            await _maybe_await(pipeline.start())
            print("✅ pipeline.start() ok")
        except Exception as e:
            print(f"⚠️ pipeline.start() failed: {e}")
    return pipeline

async def _get_audio_tracks_from_pipeline(pipeline: RealTimePipeline) -> List[Any]:
    tracks: List[Any] = []
    if hasattr(pipeline, "get_tracks"):
        try:
            got = await _maybe_await(pipeline.get_tracks())
            if isinstance(got, list):
                tracks.extend(got)
        except Exception as e:
            print(f"⚠️ pipeline.get_tracks() failed: {e}")
    if not tracks and hasattr(pipeline, "tracks"):
        try:
            got = getattr(pipeline, "tracks", [])
            if isinstance(got, list):
                tracks.extend(got)
        except Exception as e:
            print(f"⚠️ reading pipeline.tracks failed: {e}")
    if tracks:
        audio_like = []
        for t in tracks:
            kind = getattr(t, "kind", None)
            if kind is None or str(kind).lower() in ("audio", "microphone", "mic"):
                audio_like.append(t)
        if audio_like:
            tracks = audio_like
    return tracks

async def _publish_tracks(session: AgentSession, context: JobContext, tracks: List[Any]) -> bool:
    if not tracks:
        print("❌ No audio tracks available from pipeline.")
        return False
    published_any = False
    for track in tracks:
        if hasattr(session, "publish"):
            try:
                await _maybe_await(session.publish(track))
                print(f"✅ Published track via session.publish: {getattr(track, 'kind', 'audio')}")
                published_any = True
                continue
            except Exception as e:
                print(f"⚠️ session.publish() failed: {e}")
        for method_name in ("publish_track", "add_track", "add_local_track", "publish_local_track"):
            if hasattr(session, method_name):
                try:
                    await _maybe_await(getattr(session, method_name)(track))
                    print(f"✅ Published track via session.{method_name}")
                    published_any = True
                    break
                except Exception as e:
                    print(f"⚠️ session.{method_name}() failed: {e}")
        if not published_any:
            for method_name in ("publish", "add_track", "add_local_track"):
                if hasattr(context, method_name):
                    try:
                        await _maybe_await(getattr(context, method_name)(track))
                        print(f"✅ Published track via context.{method_name}")
                        published_any = True
                        break
                    except Exception as e:
                        print(f"⚠️ context.{method_name}() failed: {e}")
    if not published_any:
        print("❌ Failed to publish any audio track. The call will be silent.")
    return published_any

# =========================
# MAIN FLOW
# =========================
async def setup_agent_and_trigger_call(agent_type: str = "verification"):
    print("🚀 Starting Outbound Call System")
    print(f"📞 Target: {TARGET_PHONE_NUMBER}")
    print(f"🤖 Agent: {agent_type}")
    print("=" * 60)

    call_trigger = VideoSDKCallTrigger(VIDEOSDK_TOKEN)
    session: Optional[AgentSession] = None
    context: Optional[JobContext] = None

    try:
        print("🔍 Creating room…")
        room_id = f"outbound_{agent_type}_{int(datetime.now().timestamp())}"
        room = call_trigger.create_room(room_id)
        room_id = room["roomId"]

        agent = SimpleOutboundAgent(agent_type)
        voice = AGENT_CONFIG[agent_type]["voice"]
        pipeline = await create_voice_pipeline(voice=voice)

        room_options = RoomOptions(
            room_id=room_id,
            auth_token=VIDEOSDK_TOKEN,
            name=f"Outbound Agent - {agent_type.title()}",
            join_meeting=True,
            recording=False,
            playground=False,
        )
        context = JobContext(room_options=room_options)

        print("🔍 Creating AgentSession...")
        session = AgentSession(agent=agent, pipeline=pipeline)
        print("ℹ️ AgentSession instance created.")

        if hasattr(context, "connect"):
            await _maybe_await(context.connect())
            print("🔗 JobContext connected")

        session_task = asyncio.create_task(session.start())
        print("▶️ AgentSession started")

        print("🎛️ Gathering audio tracks from pipeline…")
        tracks = await _get_audio_tracks_from_pipeline(pipeline)
        published = await _publish_tracks(session, context, tracks)
        if not published:
            print("⚠️ No tracks published. Check SDK version or permissions.")

        print(f"✅ Agent live in room: {room_id}")
        await asyncio.sleep(2.0)

        print("📡 Triggering SIP call…")
        _ = call_trigger.trigger_sip_call(
            room_id=room_id,
            phone_number=TARGET_PHONE_NUMBER,
            caller_id=CALLER_ID,
            gateway_id=GATEWAY_ID,
        )
        print("⏱️ Waiting for call & conversation…")

        await asyncio.sleep(900)  # run up to 15 minutes
        if session_task.done():
            try:
                await session_task
            except Exception as e:
                print(f"⚠️ Session task ended with error: {e}")
    except Exception as e:
        print(f"❌ Error during setup/connection: {e}")
        import traceback
        print(traceback.format_exc())
        raise
    finally:
        try:
            if session and hasattr(session, "close"):
                await _maybe_await(session.close())
                print("ℹ️ session.close() called.")
        except Exception as e:
            print(f"⚠️ session.close() error: {e}")
        try:
            if context and hasattr(context, "shutdown"):
                await _maybe_await(context.shutdown())
                print("ℹ️ context.shutdown() called.")
        except Exception as e:
            print(f"⚠️ context.shutdown() error: {e}")

def main():
    if not VIDEOSDK_TOKEN or not GOOGLE_API_KEY:
        print("❌ Missing environment variables:")
        if not VIDEOSDK_TOKEN:
            print("   - VIDEOSDK_TOKEN")
        if not GOOGLE_API_KEY:
            print("   - GOOGLE_API_KEY")
        return

    agent_type = (sys.argv[1] if len(sys.argv) > 1 else "verification").strip()
    if agent_type not in AGENT_CONFIG:
        print("❌ Invalid agent type. Use one of:", ", ".join(AGENT_CONFIG.keys()))
        return

    confirm = input(f"\n⚠️  Make REAL call to {TARGET_PHONE_NUMBER}? (y/N): ")
    if confirm.lower() not in ("y", "yes"):
        print("❌ Cancelled")
        return

    try:
        asyncio.run(setup_agent_and_trigger_call(agent_type))
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user.")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
