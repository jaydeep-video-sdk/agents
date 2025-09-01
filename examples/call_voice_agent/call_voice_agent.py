import os
import sys
import asyncio
import re
from pathlib import Path
from dotenv import load_dotenv
from time import sleep

def setup_project_imports() -> None:
    current_dir = Path(__file__).resolve().parent
    for candidate in (current_dir, *current_dir.parents):
        if candidate.name == "agents" or (candidate / "videosdk-apis").is_dir():
            project_root = candidate
            break
    else:
        raise ImportError("Could not find project root containing videosdk-apis directory")
    videosdk_apis_path = project_root / "videosdk-apis"
    if not videosdk_apis_path.is_dir():
        raise ImportError(f"videosdk-apis directory not found at: {videosdk_apis_path}")
    p = str(videosdk_apis_path)
    if p not in sys.path:
        sys.path.insert(0, p)

setup_project_imports()
env_file = Path(__file__).resolve().parent / ".env"
if not load_dotenv(env_file):
    for parent in Path(__file__).resolve().parents:
        if load_dotenv(parent / ".env"):
            break
    else:
        load_dotenv(Path.cwd() / ".env")

from room_apis.room_apis import VideoSDKRoomApis
from call_apis.call_apis import VideoSdkCallApis
from call_webhooks_apis.call_webhooks_apis import VideoSDKWebhookApis
from webhook_server import add_session, remove_session
from videosdk.agents import Agent, AgentSession, RealTimePipeline, JobContext, RoomOptions, WorkerJob, ConversationFlow
from videosdk.plugins.google import GeminiRealtime, GeminiLiveConfig

VIDEOSDK_AUTH_TOKEN = os.getenv("VIDEOSDK_AUTH_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GATEWAY_ID = os.getenv("GATEWAY_ID")
CONTACT_NUMBER = os.getenv("CONTACT_NUMBER")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://webhook.site/86973dc0-2228-4967-897a-3b4624fcd777")

if not all([VIDEOSDK_AUTH_TOKEN, GOOGLE_API_KEY, GATEWAY_ID, CONTACT_NUMBER]):
    missing = [v for v, val in {
        "VIDEOSDK_AUTH_TOKEN": VIDEOSDK_AUTH_TOKEN,
        "GOOGLE_API_KEY": GOOGLE_API_KEY,
        "GATEWAY_ID": GATEWAY_ID,
        "CONTACT_NUMBER": CONTACT_NUMBER
    }.items() if not val]
    raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

class MyVoiceAgent(Agent):
    def __init__(self):
        super().__init__(instructions="You are a helpful voice assistant that can answer questions and help with tasks.")
    async def on_enter(self): pass
    async def on_exit(self): await self.session.say("Goodbye!")

_status_code_re = re.compile(r"API request failed \[(\d{3})\]")

def _extract_status_code_from_exception(exc: Exception):
    m = _status_code_re.search(str(exc))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

def _retry_call(fn, *args, retries: int = 3, backoff: float = 1.0, **kwargs):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            code = _extract_status_code_from_exception(e)
            if code and 500 <= code < 600 and attempt < retries:
                sleep(backoff * attempt)
                continue
            raise
    raise last_exc

def make_outbound_call(room_id: str) -> tuple:
    call_client = VideoSdkCallApis(VIDEOSDK_AUTH_TOKEN)
    webhook_client = VideoSDKWebhookApis(VIDEOSDK_AUTH_TOKEN)
    webhook_id = None
    try:
        webhook = _retry_call(webhook_client.create_webhook, WEBHOOK_BASE_URL, ["call-started","call-answered","call-ended"])
        webhook_id = getattr(webhook, "id", None)
    except Exception as e:
        print(f"create_webhook failed: {e}")
    try:
        kwargs = dict(gatewayId=GATEWAY_ID, sipCallTo=CONTACT_NUMBER, destinationRoomId=room_id, waitUntilAnswered=True, ringingTimeout=30)
        if webhook_id:
            kwargs["webhookId"] = webhook_id
        return _retry_call(call_client.make_outbound_call, **kwargs), webhook_id
    except Exception as e:
        print(f"make_outbound_call failed: {e}")
        if webhook_id:
            try:
                webhook_client.delete_webhook(webhook_id)
            except Exception:
                pass
        return None, webhook_id

async def make_outbound_call_async(room_id: str):
    return await asyncio.get_event_loop().run_in_executor(None, make_outbound_call, room_id)

async def _spawn_call_and_attach(room_id: str, session):
    call_resp, webhook_id = await make_outbound_call_async(room_id)
    add_session(room_id, session, webhook_id)
    if call_resp:
        call_id = getattr(getattr(call_resp, "data", None), "callId", None) or getattr(call_resp, "callId", None)
        status = getattr(getattr(call_resp, "data", None), "status", None) or str(call_resp)
        print(f"Call initiated. callId={call_id}, status={status}, webhook_id={webhook_id}")
    else:
        print(f"Call failed. webhook_id={webhook_id}")

async def start_session(context: JobContext) -> None:
    agent = MyVoiceAgent()
    model = GeminiRealtime(model="gemini-2.0-flash-live-001", api_key=GOOGLE_API_KEY, config=GeminiLiveConfig(voice="Leda", response_modalities=["AUDIO"]))
    session = AgentSession(agent=agent, pipeline=RealTimePipeline(model=model), conversation_flow=ConversationFlow(agent))
    try:
        await context.connect()
        await session.start()
        room_id = context.room_options.room_id
        asyncio.create_task(_spawn_call_and_attach(room_id, session))
        add_session(room_id, session, None)
        await asyncio.Event().wait()
    except Exception as e:
        print(f"Error in start_session: {e}")
        raise
    finally:
        try:
            await session.close()
            await context.shutdown()
        except Exception as e:
            print(f"Error during cleanup: {e}")
        try:
            remove_session(getattr(context.room_options, "room_id", None))
        except Exception:
            pass

def make_context() -> JobContext:
    room_options = RoomOptions(
        room_id="YOUR_MEETING_ID",
        name="VideoSDK Cascaded Agent",
        playground=True,
        auth_token=VIDEOSDK_AUTH_TOKEN,
        auto_end_session=False,
        session_timeout_seconds=300
    )
    return JobContext(room_options=room_options)

if __name__ == "__main__":
    print("Starting VideoSDK Voice Agent...")
    try:
        WorkerJob(entrypoint=start_session, jobctx=make_context()).start()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Error starting job: {e}")
        raise
