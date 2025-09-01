import os
import sys
import asyncio
import re
from pathlib import Path
from dotenv import load_dotenv
from time import sleep

def setup_project_imports() -> str:
    current_dir = Path(__file__).resolve().parent
    for candidate in (current_dir, *current_dir.parents):
        if candidate.name == "agents":
            project_root = candidate
            break
    else:
        for candidate in (current_dir, *current_dir.parents):
            if (candidate / "videosdk-apis").is_dir():
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
    print(f"✅ Added to path: {videosdk_apis_path}")
    return p

setup_project_imports()

current_dir = Path(__file__).resolve().parent
env_file = current_dir / ".env"
print(f"Looking for .env file at: {env_file}")
print(f".env file exists: {env_file.exists()}")

env_loaded = load_dotenv(env_file)
if not env_loaded:
    for parent in current_dir.parents:
        parent_env = parent / ".env"
        if parent_env.exists():
            env_loaded = load_dotenv(parent_env)
            print(f"Loaded .env from: {parent_env}")
            break
    if not env_loaded:
        cwd_env = Path.cwd() / ".env"
        if cwd_env.exists():
            env_loaded = load_dotenv(cwd_env)
            print(f"Loaded .env from: {cwd_env}")

print(f"Environment loaded: {env_loaded}")

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

print(f"VIDEOSDK_AUTH_TOKEN: {'✅ Set' if VIDEOSDK_AUTH_TOKEN else '❌ Not set'}")
print(f"GOOGLE_API_KEY: {'✅ Set' if GOOGLE_API_KEY else '❌ Not set'}")
print(f"GATEWAY_ID: {'✅ Set' if GATEWAY_ID else '❌ Not set'}")
print(f"CONTACT_NUMBER: {'✅ Set' if CONTACT_NUMBER else '❌ Not set'}")
print(f"WEBHOOK_BASE_URL: {WEBHOOK_BASE_URL}")

if not all([VIDEOSDK_AUTH_TOKEN, GOOGLE_API_KEY, GATEWAY_ID, CONTACT_NUMBER]):
    missing = []
    if not VIDESDK_AUTH_TOKEN: missing.append("VIDEOSDK_AUTH_TOKEN")
    if not GOOGLE_API_KEY: missing.append("GOOGLE_API_KEY")
    if not GATEWAY_ID: missing.append("GATEWAY_ID")
    if not CONTACT_NUMBER: missing.append("CONTACT_NUMBER")
    print("\n❌ Missing environment variables!")
    for var in missing:
        print(f"  {var}=<your_value>")
    raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

class MyVoiceAgent(Agent):
    def __init__(self):
        super().__init__(instructions="You are a helpful voice assistant that can answer questions and help with tasks.")
        self.should_greet = False

    async def on_enter(self):
        pass

    async def on_exit(self):
        await self.session.say("Goodbye!")

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
            if code is not None and 500 <= code < 600:
                if attempt == retries:
                    break
                sleep(backoff * attempt)
                continue
            raise
    raise last_exc

def make_outbound_call(room_id: str) -> tuple:
    call_client = VideoSdkCallApis(VIDEOSDK_AUTH_TOKEN)
    webhook_client = VideoSDKWebhookApis(VIDEOSDK_AUTH_TOKEN)

    webhook_id = None
    try:
        webhook = _retry_call(webhook_client.create_webhook, WEBHOOK_BASE_URL, ["call-started", "call-answered", "call-ended"], retries=3, backoff=1.0)
        webhook_id = getattr(webhook, "id", None)
        print(f"Webhook created: {webhook_id}")
    except Exception as e:
        print(f"create_webhook failed after retries: {e}")
        webhook_id = None

    try:
        kwargs = dict(
            gatewayId=GATEWAY_ID,
            sipCallTo=CONTACT_NUMBER,
            destinationRoomId=room_id,
            waitUntilAnswered=True,
            ringingTimeout=30
        )
        if webhook_id is not None:
            kwargs["webhookId"] = webhook_id
        call_response = _retry_call(call_client.make_outbound_call, **kwargs, retries=3, backoff=1.0)
        return call_response, webhook_id
    except TypeError:
        try:
            if webhook_id is not None:
                call_response = _retry_call(call_client.make_outbound_call, GATEWAY_ID, CONTACT_NUMBER, room_id, True, 30, webhook_id, retries=3, backoff=1.0)
            else:
                call_response = _retry_call(call_client.make_outbound_call, GATEWAY_ID, CONTACT_NUMBER, room_id, True, 30, retries=3, backoff=1.0)
            return call_response, webhook_id
        except Exception as e:
            print(f"make_outbound_call failed after retries: {e}")
            if webhook_id:
                try:
                    webhook_client.delete_webhook(webhook_id)
                except Exception:
                    pass
            return None, webhook_id
    except Exception as e:
        print(f"make_outbound_call failed after retries: {e}")
        if webhook_id:
            try:
                webhook_client.delete_webhook(webhook_id)
            except Exception:
                pass
        return None, webhook_id

async def make_outbound_call_async(room_id: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, make_outbound_call, room_id)

async def _spawn_call_and_attach(room_id: str, session):
    call_resp, webhook_id = await make_outbound_call_async(room_id)
    add_session(room_id, session, webhook_id)
    if call_resp:
        call_id = getattr(getattr(call_resp, "data", None), "callId", None) or getattr(call_resp, "callId", None)
        status = getattr(getattr(call_resp, "data", None), "status", None) or str(call_resp)
        print(f"Call initiated. callId={call_id}, status={status}, webhook_id={webhook_id}")
    else:
        print(f"Call failed or returned none. webhook_id={webhook_id}")

async def start_session(context: JobContext) -> None:
    agent = MyVoiceAgent()
    conversation_flow = ConversationFlow(agent)
    model = GeminiRealtime(
        model="gemini-2.0-flash-live-001",
        api_key=GOOGLE_API_KEY,
        config=GeminiLiveConfig(voice="Leda", response_modalities=["AUDIO"])
    )
    pipeline = RealTimePipeline(model=model)
    session = AgentSession(agent=agent, pipeline=pipeline, conversation_flow=conversation_flow)
    webhook_client = VideoSDKWebhookApis(VIDEOSDK_AUTH_TOKEN)

    try:
        await context.connect()
        await session.start()

        room_id = context.room_options.room_id

        asyncio.create_task(_spawn_call_and_attach(room_id, session))

        add_session(room_id, session, None)

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("Received interrupt signal, shutting down...")
    except Exception as e:
        print(f"Error in start_session: {str(e)}")
        raise
    finally:
        try:
            await session.close()
            await context.shutdown()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
        try:
            webhook_id = None
            room_id = getattr(context.room_options, "room_id", None)
            if room_id:
                remove_session(room_id)
        except Exception:
            pass

def make_context() -> JobContext:
    room_client = VideoSDKRoomApis(VIDEOSDK_AUTH_TOKEN)
    room_response = room_client.create_room()
    print(f"Created room with ID: {room_response.roomId}")
    room_options = RoomOptions(
        room_id=room_response.roomId,
        name="VideoSDK Voice Agent",
        playground=True,
        auth_token=VIDEOSDK_AUTH_TOKEN,
        auto_end_session=False,
        session_timeout_seconds=300
    )
    return JobContext(room_options=room_options)

if __name__ == "__main__":
    print("Starting VideoSDK Voice Agent...")
    print("Press Ctrl+C to stop the agent")
    try:
        job = WorkerJob(entrypoint=start_session, jobctx=make_context())
        job.start()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Error starting job: {str(e)}")
        raise
