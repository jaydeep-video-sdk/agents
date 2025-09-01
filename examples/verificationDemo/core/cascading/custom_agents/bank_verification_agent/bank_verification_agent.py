import os
import sys
import asyncio
import requests
import socket
import threading
import uuid
from typing import Optional
from flask import Flask, request, jsonify, Response

current_dir = os.path.dirname(os.path.abspath(__file__))
while current_dir and os.path.basename(current_dir) != "verificationDemo":
    parent = os.path.dirname(current_dir)
    if parent == current_dir:
        fallback = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
        if os.path.exists(os.path.join(fallback, "api")):
            sys.path.insert(0, fallback)
        break
    current_dir = parent
if current_dir and os.path.basename(current_dir) == "verificationDemo":
    sys.path.insert(0, current_dir)

from videosdk.agents import Agent, function_tool, JobContext, RoomOptions, WorkerJob, AgentSession, RealTimePipeline
from videosdk.plugins.google import GeminiRealtime, GeminiLiveConfig
from api.room_api import VideoSDKRoomClient
from api.sip_api import VideoSDKSIPClient

app: Flask = Flask(__name__)
session: Optional[AgentSession] = None
webhook_id: Optional[str] = None
loop: Optional[asyncio.AbstractEventLoop] = None

def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    _, p = s.getsockname()
    s.close()
    return int(p)

@app.route("/webhook", methods=["POST"])
def webhook() -> Response:
    global session, webhook_id, loop
    data = request.json or {}
    event = data.get("event")
    if event == "call-answered" and session and loop:
        asyncio.run_coroutine_threadsafe(
            session.say("Namaskar! Main Priya bol rahi hun ABC Bank se. Verification ke liye call kar rahi thi, 4-5 minute ka time milega?"),
            loop
        )
    if event in ("call-ended", "call-missed") and webhook_id:
        try:
            requests.delete(f"https://api.videosdk.live/v2/sip/webhooks/{webhook_id}",
                            headers={"Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlrZXkiOiI0ZjU1MWI1Yy1mYmEyLTQ0OWQtYjU5NC02MjNhYzgyMGIwZWYiLCJwZXJtaXNzaW9ucyI6WyJhbGxvd19qb2luIl0sImlhdCI6MTc1NjYzOTY2MiwiZXhwIjoxNzU3MjQ0NDYyfQ.q0Lh7ij5v62TPwNDwGagrr03TVffHPVq4N7RtHlajJo"})
        except Exception as e:
            print(f"Error deleting webhook: {e}")
        webhook_id = None
    return jsonify({"status": "ok"})

@function_tool
def verify_account(account_id: str) -> str:
    return f"Account {account_id} verified successfully."

class BankAgent(Agent):
    def __init__(self) -> None:
        self.id = "test@124"
        super().__init__(instructions="You are Priya from ABC Bank...", tools=[verify_account], agent_id=self.id)
        self.room_id: Optional[str] = None

    async def on_enter(self) -> None:
        gateway = os.getenv("SIP_GATEWAY_ID")
        target = os.getenv("TARGET_PHONE_NUMBER")
        room_id = self.room_id
        if not gateway or not target or not room_id:
            return None
        def _call() -> object:
            try:
                return VideoSDKSIPClient().trigger_call(
                    gateway_id=gateway,
                    sip_call_to=target,
                    destination_room_id=room_id,
                    participant_name="Customer"
                )
            except Exception as e:
                print(f"Error triggering call: {e}")
                return None
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _call)
        return None

    async def on_exit(self) -> None:
        global webhook_id
        try:
            await self.session.say("Dhanyawaad ji!")
        except Exception as e:
            print(f"Error saying goodbye: {e}")
        if webhook_id:
            try:
                requests.delete(f"https://api.videosdk.live/v2/sip/webhooks/{webhook_id}",
                                headers={"Authorization": os.getenv("VIDEOSDK_AUTH_TOKEN")})
            except Exception as e:
                print(f"Error deleting webhook: {e}")

async def cleanup() -> None:
    global webhook_id, session
    if webhook_id:
        try:
            requests.delete(f"https://api.videosdk.live/v2/sip/webhooks/{webhook_id}",
                          headers={"Authorization": os.getenv("VIDEOSDK_AUTH_TOKEN")})
            webhook_id = None
        except Exception as e:
            print(f"Error during webhook cleanup: {e}")
    
    if session:
        try:
            await session.stop()
            session = None
        except Exception as e:
            print(f"Error during session cleanup: {e}")

async def main(ctx: JobContext) -> None:
    global session, webhook_id, loop
    loop = asyncio.get_event_loop()

    if not os.getenv("VIDEOSDK_AUTH_TOKEN") or not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("VIDEOSDK_AUTH_TOKEN and GOOGLE_API_KEY must be set")

    port = int(os.getenv("WEBHOOK_PORT")) if os.getenv("WEBHOOK_PORT") else _free_port()
    provided = os.getenv("WEBHOOK_URL")
    webhook_url = provided if provided else f"http://localhost:{port}/webhook"
    
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, use_reloader=False, debug=False),
        daemon=True
    )
    flask_thread.start()

    try:
        # Register webhook
        try:
            r = requests.post(
                "https://api.videosdk.live/v2/sip/webhooks",
                headers={"Authorization": os.getenv("VIDEOSDK_AUTH_TOKEN"), "Content-Type": "application/json"},
                json={"url": webhook_url, "events": ["call-answered", "call-ended", "call-missed"]},
                timeout=10
            )
            webhook_id = r.json().get("id") if r.status_code == 200 else None
            if not webhook_id:
                print("Warning: Failed to register webhook")
        except Exception as e:
            print(f"Error registering webhook: {e}")

        # Initialize agent and session
        agent = BankAgent()
        agent.room_id = ctx.room_options.room_id
        session = AgentSession(
            agent=agent,
            
            pipeline=RealTimePipeline(
                GeminiRealtime(
                    model="gemini-2.0-flash-live-001",
                    api_key=os.getenv("GOOGLE_API_KEY"),
                    config=GeminiLiveConfig(voice="Leda", response_modalities=["AUDIO"])
                )
            )
        )

        # Connect and start session
        await ctx.connect()
        await session.start()

        # Wait for participant with timeout
        try:
            await asyncio.wait_for(ctx.wait_for_participant(None), timeout=30.0)
        except asyncio.TimeoutError:
            print("No participant joined within timeout period")

        # Keep the agent running until interrupted
        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        print("Received cancellation, cleaning up...")
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        await cleanup()

def create_room_direct(token: str) -> Optional[str]:
    """Create a room using direct API call"""
    try:
        response = requests.post(
            "https://api.videosdk.live/v2/rooms",
            headers={
                "Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlrZXkiOiI0ZjU1MWI1Yy1mYmEyLTQ0OWQtYjU5NC02MjNhYzgyMGIwZWYiLCJwZXJtaXNzaW9ucyI6WyJhbGxvd19qb2luIl0sImlhdCI6MTc1NjYzOTY2MiwiZXhwIjoxNzU3MjQ0NDYyfQ.q0Lh7ij5v62TPwNDwGagrr03TVffHPVq4N7RtHlajJo",
                "Content-Type": "application/json"
            },
            json={},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("roomId")
        else:
            print(f"API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error creating room: {e}")
        return None

if __name__ == "__main__":
    auth_token = os.getenv("VIDEOSDK_AUTH_TOKEN")
    if not auth_token:
        print("Error: VIDEOSDK_AUTH_TOKEN not set")
        sys.exit(1)
    
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY not set")
        sys.exit(1)
    
    # Try VideoSDKRoomClient first, fallback to direct API
    room_id = None
    try:
        response = VideoSDKRoomClient(token=auth_token, base_url="https://api.videosdk.live/v2").create_room()
        if response and hasattr(response, 'data') and response.data:
            room_id = response.data.get("roomId")
    except Exception as e:
        print(f"VideoSDKRoomClient failed: {e}")
    
    # Fallback to direct API call
    if not room_id:
        print("Trying direct API call...")
        room_id = create_room_direct(auth_token)
    
    if not room_id:
        print("Error: Failed to create room")
        sys.exit(1)
    
    print(f"Room created: {room_id}")
    
    WorkerJob(entrypoint=main, jobctx=JobContext(room_options=RoomOptions(
        room_id=room_id,
        name="Bank Agent",
        playground=True,
        auth_token=auth_token,
        signaling_base_url="api.videosdk.live",
        auto_end_session=False,
        session_timeout_seconds=None
    ))).start()