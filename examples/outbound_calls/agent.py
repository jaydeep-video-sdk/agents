from videosdk.agents import Agent, function_tool
import logging
from typing import Dict, Optional
from config import AGENT_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OutboundCallAgent(Agent):
    def __init__(self, agent_type: str):
        """
        Initialize the agent with specified type ('verification' or 'medical_feedback')
        """
        self.agent_type = agent_type
        self.config = AGENT_CONFIG[agent_type]
        
        super().__init__(
            instructions=self.config['instructions'],
            tools=[]
        )
        
        self.conversation_flow = self.config['conversation_flow']
        self.current_context = None
        self.conversation_history = []
        
    async def on_enter(self) -> None:
        """Called when the agent joins the meeting"""
        await self.session.say(self.config['greeting'])
        
    async def on_exit(self) -> None:
        """Called when the agent leaves the meeting"""
        await self.session.say(self.config['farewell'])
        
    async def start_conversation(self, context_data: Dict) -> None:
        """Initialize the conversation with context data"""
        self.current_context = {
            'data': context_data,
            'current_step': 'greeting',
            'responses': {},
            'completed_steps': set()
        }
        
        # Start with greeting
        await self.session.say(self.conversation_flow['greeting']['message'])
        
    async def handle_response(self, user_input: str) -> Dict:
        """Process user's response and determine next step"""
        if not self.current_context:
            await self.session.say("I apologize, but there's no active conversation session.")
            return {'error': 'No active session'}

        # Record the response
        self.conversation_history.append({
            'role': 'user',
            'content': user_input
        })
        
        current_step = self.current_context['current_step']
        
        # Store response
        self.current_context['responses'][current_step] = user_input
        
        # Verify response if needed
        verification_result = None
        if self.agent_type == 'verification':
            verification_result = await self._verify_response(current_step, user_input)
            if verification_result is False:
                # If verification failed, repeat the question
                await self.session.say(f"I'm sorry, that doesn't match our records. {self.conversation_flow[current_step]['message']}")
                return {'verified': False, 'next_step': current_step}
        
        # Get next step
        next_step = self.conversation_flow[current_step]['next']
        self.current_context['current_step'] = next_step
        
        # If there's a next step, say its message
        if next_step:
            await self.session.say(self.conversation_flow[next_step]['message'])
        
        return {
            'verified': verification_result if verification_result is not None else True,
            'next_step': next_step,
            'conversation_complete': next_step is None
        }
        
    async def _verify_response(self, step: str, response: str) -> bool:
        """Verify user's response against expected data (for verification agent)"""
        if self.agent_type != 'verification':
            return True
            
        expected_data = self.current_context['data']
        
        if step == 'confirm_identity':
            return response.lower() == expected_data['name'].lower()
        elif step == 'verify_dob':
            return response.replace('/', '').replace('-', '') == expected_data['dob'].replace('/', '').replace('-', '')
        elif step == 'verify_address':
            return response.lower() == expected_data['address'].lower()
            
        return True
        
    @function_tool
    async def get_conversation_status(self) -> Dict:
        """Get the current conversation status"""
        if not self.current_context:
            return {'status': 'no_active_conversation'}
            
        return {
            'current_step': self.current_context['current_step'],
            'completed_steps': list(self.current_context['completed_steps']),
            'responses': self.current_context['responses'],
            'is_complete': self.current_context['current_step'] is None
        }
        
    @function_tool
    async def get_conversation_summary(self) -> Dict:
        """Get a summary of the conversation"""
        if not self.current_context or self.current_context['current_step'] is not None:
            return {'status': 'conversation_not_complete'}
            
        summary = {
            'type': self.agent_type,
            'completed': True,
            'responses': self.current_context['responses']
        }
        
        # Add type-specific summary data
        if self.agent_type == 'medical_feedback':
            ratings = []
            for rating_step in ['rate_experience', 'service_quality']:
                try:
                    rating = int(self.current_context['responses'].get(rating_step, 0))
                    if 1 <= rating <= 5:
                        ratings.append(rating)
                except ValueError:
                    continue
                    
            summary.update({
                'visit_id': self.current_context['data']['visit_id'],
                'average_rating': sum(ratings) / len(ratings) if ratings else None,
                'improvement_feedback': self.current_context['responses'].get('improvement')
            })
        elif self.agent_type == 'verification':
            summary.update({
                'verification_id': self.current_context['data']['id'],
                'verified_fields': [
                    step for step in ['confirm_identity', 'verify_dob', 'verify_address']
                    if step in self.current_context['completed_steps']
                ]
            })
            
        return summary
