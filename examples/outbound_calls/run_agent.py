import asyncio
import os
import sys
from dotenv import load_dotenv
from videosdk.agents import AgentSession, WorkerJob, RealTimePipeline, JobContext, RoomOptions
from videosdk.plugins.google import GeminiRealtime, GeminiLiveConfig

from agent import OutboundCallAgent
from config import AGENT_CONFIG, TEST_DATA, VIDEOSDK_TOKEN, GOOGLE_API_KEY, OUTBOUND_NUMBER

# Load environment variables
load_dotenv()


async def create_pipeline(voice: str) -> RealTimePipeline:
    """Create a real-time conversation pipeline"""
    model = GeminiRealtime(
        model="gemini-2.0-flash-live-001",
        api_key=GOOGLE_API_KEY,
        config=GeminiLiveConfig(
            voice=voice,
            response_modalities=["AUDIO"]
        )
    )
    return RealTimePipeline(model=model)


async def start_agent_session(agent_type: str):
    """Start an agent session for either verification or medical feedback"""
    # Create the agent
    agent = OutboundCallAgent(agent_type)

    # Set up the pipeline with the configured voice
    pipeline = await create_pipeline(AGENT_CONFIG[agent_type]['voice'])

    # Get the test data for this agent type
    context_data = TEST_DATA[agent_type]

    # Create a unique room ID
    room_id = f"{agent_type}_{context_data.get('id', context_data.get('visit_id'))}"

    # Create room options
    room_options = RoomOptions(
        room_id=room_id,
        auth_token=VIDEOSDK_TOKEN,
        name=AGENT_CONFIG[agent_type]['name'],
        playground=True
    )

    # Create job context
    context = JobContext(room_options=room_options)

    # Create the agent session
    session = AgentSession(
        agent=agent,
        pipeline=pipeline
    )

    try:
        # Connect to the room
        await context.connect()

        # Start the conversation
        await agent.start_conversation(context_data)

        # Start the session
        await session.start()

        # Keep the session running
        await asyncio.Event().wait()
    finally:
        await session.close()
        await context.shutdown()


# Global variable to store agent type
agent_type = 'verification'


async def agent_entrypoint(ctx):
    """Entrypoint coroutine for WorkerJob"""
    await start_agent_session(agent_type)


def create_job_context() -> JobContext:
    """Create a default JobContext (required by WorkerJob)"""
    return JobContext(
        room_options=RoomOptions(
            room_id="default-room",
            auth_token=VIDEOSDK_TOKEN,
            name="DefaultAgent",
            playground=True
        )
    )


async def run_agent():
    """Run the agent with the specified type"""
    global agent_type

    # Check for agent type argument
    agent_type = sys.argv[1] if len(sys.argv) > 1 else 'verification'

    if agent_type not in ['verification', 'medical_feedback']:
        print("Invalid agent type. Please use 'verification' or 'medical_feedback'")
        sys.exit(1)

    # ✅ FIX: pass function reference, not object
    job = WorkerJob(
        entrypoint=agent_entrypoint,
        jobctx=create_job_context
    )

    job.start()

    try:
        # Keep the event loop running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\nShutting down agent...")
        job.stop()


def main():
    """Main function to run the agents"""
    if not all([VIDEOSDK_TOKEN, GOOGLE_API_KEY, OUTBOUND_NUMBER]):
        raise ValueError(
            "Please set all required environment variables:\n"
            "- VIDEOSDK_TOKEN\n"
            "- GOOGLE_API_KEY\n"
            "- OUTBOUND_NUMBER"
        )

    asyncio.run(run_agent())


if __name__ == "__main__":
    main()
