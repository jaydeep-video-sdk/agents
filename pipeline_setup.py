from videosdk.plugins.google import GeminiRealtime, GeminiLiveConfig
from videosdk.agents import RealTimePipeline, JobContext
import os

class PipelineManager:
    @staticmethod
    async def create_pipeline(model_name: str = "gemini-2.0-flash-live-001", voice: str = "Leda"):
        """Create a real-time pipeline for conversation"""
        model = GeminiRealtime(
            model=model_name,
            api_key=os.getenv("GOOGLE_API_KEY"),
            config=GeminiLiveConfig(
                voice=voice,
                response_modalities=["AUDIO"]
            )
        )
        
        return RealTimePipeline(model=model)

    @staticmethod
    def create_job_context(room_id: str, auth_token: str, agent_name: str) -> JobContext:
        """Create a job context for the agent"""
        room_options = RoomOptions(
            room_id=room_id,
            auth_token=auth_token,
            name=agent_name,
            playground=True
        )
        
        return JobContext(room_options=room_options)
