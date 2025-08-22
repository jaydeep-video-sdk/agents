from videosdk.agents import Agent, function_tool
from videosdk.agents import AgentSession, RoomOptions
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseAgent(Agent):
    def __init__(self, instructions: str, name: str):
        super().__init__(
            instructions=instructions,
            tools=[]  # Will be populated by child classes
        )
        self.name = name
        self.current_session = None
        self.conversation_history = []
        
    async def on_enter(self) -> None:
        """Called when the agent joins the meeting"""
        self.current_session = self.session
        welcome_msg = f"Hello, I am {self.name}. How can I assist you today?"
        await self.session.say(welcome_msg)
        
    async def on_exit(self) -> None:
        """Called when the agent leaves the meeting"""
        goodbye_msg = "Thank you for your time. Goodbye!"
        await self.session.say(goodbye_msg)
        
    async def handle_response(self, user_input: str) -> None:
        """Handle user response and maintain conversation history"""
        self.conversation_history.append({"role": "user", "content": user_input})
        
    @function_tool
    async def get_conversation_history(self) -> list:
        """Return the conversation history"""
        return self.conversation_history
    
    @function_tool
    async def clear_conversation_history(self) -> None:
        """Clear the conversation history"""
        self.conversation_history = []
        
    async def create_meeting(self, auth_token: str) -> str:
        """Create a new VideoSDK meeting"""
        # Implementation for creating a new meeting using VideoSDK API
        pass
        
    async def join_meeting(self, meeting_id: str, auth_token: str) -> None:
        """Join an existing VideoSDK meeting"""
        room_options = RoomOptions(
            room_id=meeting_id,
            auth_token=auth_token,
            name=self.name,
            playground=True
        )
        
        # Join the meeting
        await self.session.join(room_options)
