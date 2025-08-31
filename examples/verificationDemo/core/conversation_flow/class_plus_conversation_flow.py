import random
from typing import AsyncIterator, Dict, List
from videosdk.agents.conversation_flow import ConversationFlow
from videosdk.agents import ChatRole


class ClassPlusConversationFlow(ConversationFlow):
    def __init__(self, agent, stt=None, llm=None, tts=None, vad=None, turn_detector=None):
        super().__init__(agent, stt, llm, tts, vad, turn_detector)
        self.conversation_step: int = 0
        self.lead_data: Dict[str, object] = {
            "name": "",
            "profession": "",
            "subjects": [],
            "student_count": 0,
            "city": "",
            "state": "",
            "has_youtube": False,
            "interest_level": "unknown",
        }
        self.conversation_state: str = "greeting"
        self.objections_raised: List[str] = []
        self.enthusiasm_level: str = "neutral"
        self.is_turn_active: bool = False

    async def run(self, transcript: str) -> AsyncIterator[str]:
        await self.on_turn_start(transcript)
        user_input = transcript.strip()
        sentiment = self._analyze_user_sentiment(user_input)
        response_type = self._classify_response_type(user_input)
        acknowledgment = self._get_natural_acknowledgment(user_input, sentiment)
        enhanced_prompt = self._build_contextual_prompt(user_input, acknowledgment, sentiment, response_type)

        try:
            if hasattr(self.agent, "chat_context") and hasattr(self.agent.chat_context, "add_message"):
                self.agent.chat_context.add_message(role=ChatRole.USER, content=enhanced_prompt)
        except Exception:
            pass

        async for response_chunk in self.process_with_llm():
            yield response_chunk

        await self.on_turn_end()

    def _analyze_user_sentiment(self, user_input: str) -> str:
        user_lower = user_input.lower()
        positive_keywords = [
            "interested", "good", "nice", "accha", "theek", "bahut accha", "great", "wow", "amazing",
            "helpful", "sounds good", "tell me more", "tell me", "sure"
        ]
        negative_keywords = [
            "not interested", "no thanks", "busy", "waste", "nahi chahiye", "expensive", "costly",
            "problem", "issue", "difficult"
        ]
        confused_keywords = ["kya", "how", "samajh nahi", "confused", "explain", "batao", "kaise"]

        if any(k in user_lower for k in positive_keywords):
            self.enthusiasm_level = "high"
            return "positive"
        if any(k in user_lower for k in negative_keywords):
            self.enthusiasm_level = "low"
            return "negative"
        if any(k in user_lower for k in confused_keywords):
            return "confused"
        return "neutral"

    def _classify_response_type(self, user_input: str) -> str:
        user_lower = user_input.lower()
        if any(w in user_lower for w in ["yes", "haan", "ji haan", "bilkul"]):
            return "agreement"
        if any(w in user_lower for w in ["no", "nahi", "nahin"]):
            return "disagreement"
        if "?" in user_input or any(w in user_lower for w in ["kya", "kaise", "kab", "kyun", "how", "what", "when", "why"]):
            return "question"
        if any(w in user_lower for w in ["teacher", "students", "coaching", "padhata", "classes"]):
            return "information"
        if any(w in user_lower for w in ["price", "cost", "kitna", "paisa", "expensive", "cheap"]):
            return "price_inquiry"
        if any(w in user_lower for w in ["time", "samay", "busy", "later", "baad mein"]):
            return "time_concern"
        return "general"

    def _get_natural_acknowledgment(self, user_input: str, sentiment: str) -> str:
        acknowledgments = {
            "positive": [
                "Arre wah! Yeh toh bahut accha laga sunke!",
                "Bilkul sir/madam! Aap sahi keh rahe hain!",
                "Haan ji haan! Exactly mere khyaal se bhi!",
                "Perfect! Main bhi yahi soch rahi thi!",
                "Arre bahut accha! You're so right about this!"
            ],
            "negative": [
                "Haan ji, main samjh sakti hun aapki concern...",
                "Accha accha, no problem ji...",
                "Theek hai sir/madam, main explain karti hun...",
                "Koi baat nahi ji, yeh natural hai feel karna...",
                "Samjh gaya main aapki baat..."
            ],
            "confused": [
                "Arre haan ji, main properly explain karti hun...",
                "Accha sorry, main clearly nahi bola... let me tell you...",
                "Bilkul! Main step by step batati hun...",
                "Haan ji, yeh confusing lag sakta hai initially...",
                "No problem ji, main detail mein samjhati hun..."
            ],
            "neutral": [
                "Haan ji, samjh gaya...",
                "Accha accha, theek hai...",
                "Right right...",
                "Hmm, okay ji...",
                "Bilkul, note kar liya..."
            ]
        }
        choices = acknowledgments.get(sentiment, acknowledgments["neutral"]).copy()
        if len(user_input) > 50:
            choices.extend([
                "Wow, aapne detail mein bataya! Main note kar rahi hun...",
                "Arre thank you itni information dene ke liye!",
                "Accha accha, bahut saari details mil gayi..."
            ])
        return random.choice(choices) if choices else ""

    def _build_contextual_prompt(self, user_input: str, acknowledgment: str, sentiment: str, response_type: str) -> str:
        stage_contexts = {
            "greeting": {"context": "Just started the call, building rapport and confirming identity", "goal": "Confirm you're speaking to the right person and transition to discovery", "style": "Warm, friendly, professional but casual"},
            "discovery": {"context": "Learning about their teaching background and current setup", "goal": "Understand their profession, student count, subjects, and current challenges", "style": "Curious, interested, asking natural follow-up questions"},
            "pitch": {"context": "Explaining ClassPlus benefits and success stories", "goal": "Show value proposition, share success stories, create interest", "style": "Enthusiastic but not pushy, storytelling, relatable examples"},
            "demo": {"context": "Discussing demo scheduling and next steps", "goal": "Book a demo slot, create urgency, handle objections", "style": "Helpful, solution-focused, creating gentle urgency"},
            "closing": {"context": "Finalizing the call outcome and next steps", "goal": "Confirm next steps, thank them, leave positive impression", "style": "Grateful, professional, ensuring clarity on follow-up"}
        }
        current_context = stage_contexts.get(self.conversation_state, stage_contexts["discovery"])
        response_guidance = {
            "agreement": "They agreed! Show enthusiasm and move forward naturally",
            "disagreement": "They disagreed. Don't argue, understand their concern and address gently",
            "question": "They asked a question. Answer thoroughly but conversationally",
            "information": "They shared info. Acknowledge, show interest, ask natural follow-ups",
            "price_inquiry": "Price question. Don't just give numbers, explain value first",
            "time_concern": "Time issue. Be understanding, offer flexible options"
        }
        enhanced_prompt = f"""{acknowledgment}

Customer just said: "{user_input}"

CONVERSATION CONTEXT:
- Current stage: {self.conversation_state}
- Stage goal: {current_context['goal']}
- Customer sentiment: {sentiment}
- Response type: {response_type}
- Their enthusiasm level: {self.enthusiasm_level}

RESPONSE GUIDANCE:
- {response_guidance.get(response_type, 'Respond naturally to their input')}
- Style: {current_context['style']}

CURRENT LEAD DATA:
- Name: {self.lead_data.get('name', 'Unknown')}
- Profession: {self.lead_data.get('profession', 'Unknown')}
- Student count: {self.lead_data.get('student_count', 'Unknown')}
- Interest level: {self.lead_data.get('interest_level', 'Unknown')}

INSTRUCTIONS:
You are Priya from ClassPlus. Respond in natural Hinglish conversation style.
- Use the acknowledgment I provided, then continue naturally
- Match their energy level (if excited, be excited; if hesitant, be understanding)
- Ask ONE natural follow-up question to keep conversation flowing
- Don't overwhelm with too much information at once
- Use 'ji', 'aap', 'accha' naturally in speech
- If they shared information, acknowledge it specifically before moving forward
- Keep responses conversational length (2-4 sentences max unless they asked for details)

AVOID:
- Robotic or scripted responses
- Overwhelming with too much info
- Being pushy if they're hesitant
- Ignoring their specific concern or question
"""
        return enhanced_prompt

    def _update_lead_data(self, user_input: str) -> None:
        user_lower = user_input.lower()
        professions = {
            "teacher": ["teacher", "sir", "madam", "padhata", "padhati"],
            "coaching": ["coaching", "institute", "classes"],
            "youtuber": ["youtube", "channel", "video"],
            "student": ["student", "college", "school"]
        }
        for profession, keywords in professions.items():
            if any(k in user_lower for k in keywords):
                self.lead_data["profession"] = profession
                break
        import re
        nums = re.findall(r"\d+", user_input)
        if nums:
            for n in sorted(map(int, nums), reverse=True):
                if 1 <= n <= 10000:
                    self.lead_data["student_count"] = n
                    break
        subjects = ["math", "english", "science", "physics", "chemistry", "biology", "commerce", "accounts", "economics", "computer", "programming"]
        found_subjects = [s for s in subjects if s in user_lower]
        for s in found_subjects:
            if s not in self.lead_data["subjects"]:
                self.lead_data["subjects"].append(s)

    def _determine_next_conversation_state(self, user_input: str, sentiment: str) -> None:
        user_lower = user_input.lower()
        if any(w in user_lower for w in ["demo", "show", "dikhao", "presentation"]):
            self.conversation_state = "demo"
            return
        if any(w in user_lower for w in ["not interested", "nahi chahiye", "busy"]):
            return
        if sentiment == "positive":
            if self.conversation_state in ("greeting", "discovery"):
                self.conversation_state = "pitch"
            else:
                self.conversation_state = "demo"
        elif sentiment == "negative":
            self.conversation_state = "pitch"

    async def on_turn_start(self, transcript: str) -> None:
        self.is_turn_active = True
        print(f"📝 Customer: {transcript}")

    async def on_turn_end(self) -> None:
        self.is_turn_active = False
        self.conversation_step += 1
        if self.conversation_step == 1:
            greeting = getattr(self.agent.config, "greeting", "")
            try:
                if hasattr(self.agent, "chat_context") and hasattr(self.agent.chat_context, "add_system_message"):
                    self.agent.chat_context.add_system_message("SYSTEM: " + greeting)
            except Exception:
                pass
            print(f"🤖 AGENT: {greeting}")
            self.conversation_state = "greeting"
            self.enthusiasm_level = "high"
        print(f"✅ Turn {self.conversation_step} completed")
        print(f"📊 Current State: {self.conversation_state}")
        print("-" * 50)

    def get_conversation_summary(self) -> Dict[str, object]:
        return {
            "total_turns": self.conversation_step,
            "final_state": self.conversation_state,
            "lead_data": self.lead_data,
            "enthusiasm_level": self.enthusiasm_level,
            "objections_raised": self.objections_raised,
        }
