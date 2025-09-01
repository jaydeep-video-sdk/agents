import os
import asyncio
import uuid
from dotenv import load_dotenv

load_dotenv()

from videosdk.agents import Agent, AgentSession, RealTimePipeline, JobContext, RoomOptions, WorkerJob, ConversationFlow
from videosdk.plugins.google import GeminiRealtime, GeminiLiveConfig
from videosdk_apis.room_apis.room_apis import VideoSDKRoomApis

VIDEOSDK_AUTH_TOKEN = os.getenv("VIDEOSDK_AUTH_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not VIDEOSDK_AUTH_TOKEN:
    raise ValueError("VIDEOSDK_AUTH_TOKEN is missing in your environment")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is missing in your environment")

class MyVoiceAgent(Agent):
    def __init__(self):
        super().__init__(instructions="You are a helpful voice assistant that can answer questions and help with tasks.")
    
    async def on_enter(self):
        await self.session.say("Hello! How can I help?")
    
    async def on_exit(self):
        await self.session.say("Goodbye!")

async def start_session(context: JobContext):
    agent = MyVoiceAgent()
    conversation_flow = ConversationFlow(agent)

    model = GeminiRealtime(
        model="gemini-2.0-flash-live-001",
        api_key=GOOGLE_API_KEY,
        config=GeminiLiveConfig(
            voice="Leda",
            response_modalities=["AUDIO"]
        )
    )

    pipeline = RealTimePipeline(model=model)
    session = AgentSession(
        agent=agent,
        pipeline=pipeline,
        conversation_flow=conversation_flow
    )

    try:
        await context.connect()
        await session.start()
        await asyncio.Event().wait()
    finally:
        await session.close()
        await context.shutdown()

def make_context() -> JobContext:
    room_client = VideoSDKRoomApis(VIDEOSDK_AUTH_TOKEN)
    room_response = room_client.create_room()
    room_options = RoomOptions(
        room_id=room_response.roomId,
        name="VideoSDK Voice Agent",
        playground=True,
        auth_token=VIDEOSDK_AUTH_TOKEN
    )
    return JobContext(room_options=room_options)

if __name__ == "__main__":
    job = WorkerJob(entrypoint=start_session, jobctx=make_context)
    job.start()