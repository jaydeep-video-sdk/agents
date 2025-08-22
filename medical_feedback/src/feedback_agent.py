from typing import Dict, Optional
import logging
from ...base_agent import BaseAgent
from .utils import VideoSDKClient
from .config import VIDEO_SDK_TOKEN, GATEWAY_CONFIG, FEEDBACK_STEPS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MedicalFeedbackAgent(BaseAgent):
    def __init__(self):
        self.client = VideoSDKClient(VIDEO_SDK_TOKEN)
        self.gateway_id = None
        self.current_feedback = None

    def setup_gateway(self, numbers: list[str]) -> str:
        """Set up the outbound gateway for feedback calls"""
        try:
            response = self.client.create_outbound_gateway(
                name=GATEWAY_CONFIG['name'],
                numbers=numbers,
                address=GATEWAY_CONFIG['address']
            )
            self.gateway_id = response['gatewayId']
            logger.info(f"Gateway created with ID: {self.gateway_id}")
            return self.gateway_id
        except Exception as e:
            logger.error(f"Failed to create gateway: {str(e)}")
            raise

    def start_feedback_call(self, to_number: str, from_number: str, visit_data: Dict) -> Dict:
        """Start a feedback call"""
        try:
            # Create a unique room for this feedback session
            room_id = f"feedback_{visit_data.get('visit_id', 'unknown')}"
            
            # Store feedback context
            self.current_feedback = {
                'visit_id': visit_data.get('visit_id'),
                'patient_name': visit_data.get('patient_name'),
                'visit_date': visit_data.get('visit_date'),
                'department': visit_data.get('department'),
                'current_step': 'greeting',
                'responses': {}
            }

            # Trigger the call
            response = self.client.trigger_call(
                gateway_id=self.gateway_id,
                to_number=to_number,
                from_number=from_number,
                room_id=room_id,
                context={'visit_id': visit_data.get('visit_id')}
            )

            logger.info(f"Started feedback call: {response['callId']}")
            return response
        except Exception as e:
            logger.error(f"Failed to start feedback call: {str(e)}")
            raise

    def process_response(self, user_response: str) -> Dict:
        """Process user's response and determine next step"""
        if not self.current_feedback:
            raise ValueError("No active feedback session")

        current_step = self.current_feedback['current_step']
        
        # Store the response
        self.current_feedback['responses'][current_step] = user_response
        
        # Get next step
        next_step = FEEDBACK_STEPS[current_step]['next']
        self.current_feedback['current_step'] = next_step

        return {
            'response_recorded': True,
            'next_step': next_step,
            'next_message': FEEDBACK_STEPS[next_step]['message'] if next_step else None,
            'feedback_complete': next_step is None
        }

    def validate_rating(self, response: str) -> Optional[int]:
        """Validate numerical rating responses"""
        try:
            rating = int(response)
            if 1 <= rating <= 5:
                return rating
        except ValueError:
            pass
        return None

    def get_feedback_status(self) -> Dict:
        """Get the current feedback status"""
        if not self.current_feedback:
            return {'status': 'no_active_feedback'}

        return {
            'visit_id': self.current_feedback['visit_id'],
            'current_step': self.current_feedback['current_step'],
            'is_complete': self.current_feedback['current_step'] is None,
            'responses': self.current_feedback['responses']
        }

    def get_feedback_summary(self) -> Dict:
        """Get a summary of the feedback once completed"""
        if not self.current_feedback or self.current_feedback['current_step'] is not None:
            return {'status': 'feedback_not_complete'}

        responses = self.current_feedback['responses']
        
        # Calculate average rating if numerical ratings were provided
        ratings = []
        if 'rate_experience' in responses:
            rating = self.validate_rating(responses['rate_experience'])
            if rating:
                ratings.append(rating)
        if 'service_quality' in responses:
            rating = self.validate_rating(responses['service_quality'])
            if rating:
                ratings.append(rating)

        avg_rating = sum(ratings) / len(ratings) if ratings else None

        return {
            'visit_id': self.current_feedback['visit_id'],
            'patient_name': self.current_feedback['patient_name'],
            'visit_date': self.current_feedback['visit_date'],
            'department': self.current_feedback['department'],
            'average_rating': avg_rating,
            'improvement_feedback': responses.get('improvement'),
            'visit_confirmed': responses.get('confirm_visit', '').lower() in ['yes', 'true', '1'],
            'complete': True
        }
