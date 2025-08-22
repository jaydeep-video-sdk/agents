from typing import Dict, Optional
import logging
from ...base_agent import BaseAgent
from .utils import VideoSDKClient
from .config import VIDEO_SDK_TOKEN, GATEWAY_CONFIG, VERIFICATION_STEPS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IDVerificationAgent(BaseAgent):
    def __init__(self):
        self.client = VideoSDKClient(VIDEO_SDK_TOKEN)
        self.gateway_id = None
        self.current_verification = None

    def setup_gateway(self, numbers: list[str]) -> str:
        """Set up the outbound gateway for verification calls"""
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

    def start_verification(self, to_number: str, from_number: str, verification_data: Dict) -> Dict:
        """Start a verification call"""
        try:
            # Create a unique room for this verification
            room_id = f"verify_{verification_data.get('id', 'unknown')}"
            
            # Store verification context
            self.current_verification = {
                'id': verification_data.get('id'),
                'expected_name': verification_data.get('name'),
                'expected_dob': verification_data.get('dob'),
                'expected_address': verification_data.get('address'),
                'current_step': 'greeting',
                'verified_fields': set()
            }

            # Trigger the call
            response = self.client.trigger_call(
                gateway_id=self.gateway_id,
                to_number=to_number,
                from_number=from_number,
                room_id=room_id,
                context={'verification_id': verification_data.get('id')}
            )

            logger.info(f"Started verification call: {response['callId']}")
            return response
        except Exception as e:
            logger.error(f"Failed to start verification: {str(e)}")
            raise

    def process_response(self, user_response: str) -> Dict:
        """Process user's response and determine next step"""
        if not self.current_verification:
            raise ValueError("No active verification session")

        current_step = self.current_verification['current_step']
        verification_result = self._verify_response(current_step, user_response)
        
        next_step = VERIFICATION_STEPS[current_step]['next']
        self.current_verification['current_step'] = next_step

        return {
            'verified': verification_result,
            'next_step': next_step,
            'next_message': VERIFICATION_STEPS[next_step]['message'] if next_step else None,
            'verification_complete': next_step is None
        }

    def _verify_response(self, step: str, response: str) -> bool:
        """Verify user's response against expected data"""
        verification_data = self.current_verification
        
        if step == 'confirm_identity':
            if response.lower() == verification_data['expected_name'].lower():
                verification_data['verified_fields'].add('name')
                return True
        elif step == 'verify_dob':
            if response.replace('/', '').replace('-', '') == verification_data['expected_dob'].replace('/', '').replace('-', ''):
                verification_data['verified_fields'].add('dob')
                return True
        elif step == 'verify_address':
            if response.lower() == verification_data['expected_address'].lower():
                verification_data['verified_fields'].add('address')
                return True
        
        return False

    def get_verification_status(self) -> Dict:
        """Get the current verification status"""
        if not self.current_verification:
            return {'status': 'no_active_verification'}

        return {
            'verification_id': self.current_verification['id'],
            'verified_fields': list(self.current_verification['verified_fields']),
            'current_step': self.current_verification['current_step'],
            'is_complete': self.current_verification['current_step'] is None,
            'all_fields_verified': len(self.current_verification['verified_fields']) == 3
        }
