import aiohttp
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class MeetingManager:
    def __init__(self, auth_token: str):
        self.auth_token = auth_token
        self.base_url = "https://api.videosdk.live/v2"
        self.headers = {
            "Authorization": auth_token,
            "Content-Type": "application/json"
        }
    
    async def create_meeting(self) -> Dict:
        """Create a new VideoSDK meeting"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/rooms",
                headers=self.headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Created meeting with ID: {data.get('roomId')}")
                    return data
                else:
                    error_msg = await response.text()
                    logger.error(f"Failed to create meeting: {error_msg}")
                    raise Exception(f"Failed to create meeting: {error_msg}")
    
    async def validate_meeting(self, meeting_id: str) -> bool:
        """Validate if a meeting exists"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/rooms/{meeting_id}",
                headers=self.headers
            ) as response:
                return response.status == 200
    
    async def end_meeting(self, meeting_id: str) -> bool:
        """End a VideoSDK meeting"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/rooms/{meeting_id}/end",
                headers=self.headers
            ) as response:
                if response.status == 200:
                    logger.info(f"Ended meeting: {meeting_id}")
                    return True
                else:
                    error_msg = await response.text()
                    logger.error(f"Failed to end meeting {meeting_id}: {error_msg}")
                    return False
    
    async def get_meeting_token(self, meeting_id: str) -> Optional[str]:
        """Get a token for joining a specific meeting"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/token",
                headers=self.headers,
                json={"roomId": meeting_id}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("token")
                else:
                    error_msg = await response.text()
                    logger.error(f"Failed to get meeting token: {error_msg}")
                    return None
