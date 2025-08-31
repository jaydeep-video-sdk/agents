import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from videosdk.agents import Agent
from videosdk.agents.utils import function_tool


@dataclass
class ClassPlusConfig:
    model: str = "gemini-2.0-flash-live-001"
    voice: str = "Leda"
    language: str = "hi-IN"
    greeting: str = "Namaste ji! Aap kaise hain? Main Priya hoon ClassPlus se. Am I speaking to {contact_name}?"
    farewell: str = "Dhanyavaad ji! Aapka din shubh ho."
    target_number: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.target_number:
            self.target_number = os.getenv("TARGET_PHONE_NUMBER")


class ClassPlusAgent(Agent):
    def __init__(self, config: ClassPlusConfig):
        self.config: ClassPlusConfig = config
        self.room_id: Optional[str] = None
        self.call_active: bool = False
        self.state: Dict[str, Any] = {}
        # tools = [
        #     self.handle_natural_conversation,
        #     self.schedule_demo,
        #     self.validate_phone_number,
        #     self.get_current_offers,
        #     self.end_call
        # ]
        super().__init__(instructions=self.config.greeting, 
        # tools=tools
        )
        logger.info("🤖 ClassPlusAgent initialized")

    async def on_enter(self) -> None:
        logger.info("🚀 Agent entering room: %s", self.room_id)
        self.state = {"lead": {"contact_number": self.config.target_number or ""}}
        greeting_text = self.config.greeting.format(contact_name="")
        try:
            await self.session.say(greeting_text)
        except Exception:
            logger.info("session.say not available")

    async def on_participant_joined(self, participant_id: str) -> None:
        logger.info("👤 Participant joined: %s", participant_id)
        self.call_active = True
        await self._start_flow()

    async def on_participant_left(self, participant_id: str) -> None:
        logger.info("👋 Participant left: %s", participant_id)
        self.call_active = False
        try:
            await self.session.say(self.config.farewell)
        except Exception:
            logger.info("session.say not available")
        await self._finalize_and_leave()
        
    async def on_exit(self) -> None:
        """Called when the agent is exiting. Clean up resources here."""
        logger.info("✅ Agent exiting")
        self.call_active = False

    async def _start_flow(self) -> None:
        await asyncio.sleep(0.5)
        try:
            await self.session.say("Aap currently kaise padhate hain — offline, online ya dono?")
        except Exception:
            logger.info("session.say not available")

    async def _finalize_and_leave(self) -> None:
        await asyncio.sleep(0.5)
        try:
            await self.session.leave()
        except Exception:
            logger.info("session.leave failed")

    async def _save_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        return {"saved": True, "lead_id": "cp_1"}

    @function_tool
    async def handle_natural_conversation(self, user_input: str, context: str) -> str:
        import random
        acks: List[str] = ["Haan ji, samajh gaya", "Accha ji", "Bilkul ji"]
        responses: Dict[str, List[str]] = {
            "greeting": ["Aap kaise hain? Main ClassPlus ke baare mein thoda batana chahungi."],
            "interest": ["Great! Humari team aapko demo dikha degi. Kab convenient hai?"]
        }
        base: str = responses.get(context, ["Thik hai ji"])[0]
        return f"{random.choice(acks)}. {base}"

    @function_tool
    async def schedule_demo(self, demo_type: str, date: str, time_str: str, language: str) -> Dict[str, Any]:
        demo: Dict[str, Any] = {"demo_scheduled": True, "demo_type": demo_type, "date": date, "time": time_str, "language": language}
        self.state["demo"] = demo
        return demo

    @function_tool
    async def validate_phone_number(self, phone: str) -> Dict[str, Any]:
        digits = "".join(ch for ch in phone if ch.isdigit())
        valid: bool = 10 <= len(digits) <= 15
        formatted: str = digits if valid else phone
        return {"valid": valid, "formatted": formatted}

    @function_tool
    async def get_current_offers(self) -> Dict[str, Any]:
        offers: Dict[str, Any] = {
            "independence_day_offer": {"discount_percent": 40, "free_kit": True},
            "starter_price": 20000
        }
        return offers

    @function_tool
    async def end_call(self, outcome: str, comments: str = "") -> Dict[str, Any]:
        self.state["outcome"] = {"outcome": outcome, "comments": comments, "ended_at": time.time()}
        await self._save_lead(self.state.get("lead", {}))
        return {"ended": True, "outcome": outcome}


def create_classplus_agent(target_number: Optional[str] = None, language: str = "hi-IN") -> ClassPlusAgent:
    cfg = ClassPlusConfig(target_number=target_number, language=language)
    return ClassPlusAgent(cfg)
