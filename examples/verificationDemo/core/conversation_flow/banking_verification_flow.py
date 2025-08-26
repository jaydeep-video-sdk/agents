import random
from typing import AsyncIterator
from videosdk.agents.conversation_flow import ConversationFlow
from videosdk.agents import (
    ConversationFlow,
    ChatRole,
)

class BankingVerificationFlow(ConversationFlow):
    def __init__(self, agent, stt=None, llm=None, tts=None, vad=None, turn_detector=None):
        super().__init__(agent, stt, llm, tts, vad, turn_detector)
        self.verification_step = 0
        self.customer_responses = {}
        
    async def run(self, transcript: str) -> AsyncIterator[str]:
        await self.on_turn_start(transcript)
        
        user_input = transcript.strip()
        acknowledgment = self._get_hindi_acknowledgment(user_input)
        enhanced_prompt = self._build_enhanced_prompt(user_input, acknowledgment)
        self.agent.chat_context.add_message(role=ChatRole.USER, content=enhanced_prompt)
        async for response_chunk in self.process_with_llm():
            yield response_chunk
        await self.on_turn_end()

    def _get_hindi_acknowledgment(self, user_input: str) -> str:
        user_lower = user_input.lower()
        
        if any(word in user_lower for word in ['haan', 'ji', 'yes', 'theek', 'sahi']):
            return random.choice(["Bahut accha!", "Perfect!", "Bilkul sahi!", "Theek hai..."])
        
        elif any(word in user_lower for word in ['nahi', 'no', 'galat']):
            return random.choice(["Accha samajh gaya...", "Koi baat nahi...", "Theek hai phir..."])
        
        elif any(word in user_lower for word in ['kya', 'samajh', 'confused']):
            return random.choice(["Main explain karti hun...", "Dekho, slowly batati hun...", "Aap tension mat lo..."])
        
        elif len(user_input) > 20:  # Detailed response
            return random.choice(["Accha accha...", "Haan samajh gayi...", "Note kar liya..."])
        
        return ""

    def _build_enhanced_prompt(self, user_input: str, acknowledgment: str) -> str:
        """Build enhanced prompt with natural flow"""
        
        # Add context based on verification step
        context_hints = {
            0: "Customer just joined the call, need to verify their identity politely",
            1: "Getting basic information like name and address", 
            2: "Verifying documents like PAN card and Aadhar",
            3: "Checking employment and income details",
            4: "Wrapping up verification process"
        }
        
        step_context = context_hints.get(self.verification_step % 5, "Continue verification naturally")
        
        enhanced_input =    f"""
                            {acknowledgment}
                            
                            Customer said: "{user_input}"
                            
                            Context: {step_context}
                            Respond naturally in Hindi with English mix like Priya from ABC Bank would.
                            Keep it conversational and human-like.
                            """
        
        return enhanced_input

    async def on_turn_start(self, transcript: str) -> None:
        self.is_turn_active = True
        print(f"📝 Customer: {transcript}")

    async def on_turn_end(self) -> None:
        self.is_turn_active = False
        self.verification_step += 1
        print(f"✅ Step {self.verification_step} completed")
