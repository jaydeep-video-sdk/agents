import os
from typing import Dict

# Load environment variables
VIDEOSDK_TOKEN = os.getenv('VIDEOSDK_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
OUTBOUND_NUMBER = os.getenv('OUTBOUND_NUMBER')

# Agent Configuration
AGENT_CONFIG = {
    'verification': {
        'name': 'ID Verification Assistant',
        'voice': 'Leda',  # Options: Leda, Charon, Puck, etc.
        'instructions': """You are an AI agent responsible for identity verification. 
        Follow the verification steps carefully and maintain a professional tone.""",
        'greeting': 'Hello, I am the identity verification assistant. I will help verify your identity today.',
        'farewell': 'Thank you for completing the verification process. Have a great day!',
        'conversation_flow': {
            'greeting': {
                'message': 'I need to verify your identity. I will ask you a few questions.',
                'next': 'confirm_identity'
            },
            'confirm_identity': {
                'message': 'Please state your full name exactly as it appears on your ID.',
                'next': 'verify_dob'
            },
            'verify_dob': {
                'message': 'Please state your date of birth in MM/DD/YYYY format.',
                'next': 'verify_address'
            },
            'verify_address': {
                'message': 'Please state your current address exactly as it appears on your ID.',
                'next': 'completion'
            },
            'completion': {
                'message': 'Thank you. Your identity has been verified.',
                'next': None
            }
        }
    },
    'medical_feedback': {
        'name': 'Medical Feedback Assistant',
        'voice': 'Charon',  # Options: Leda, Charon, Puck, etc.
        'instructions': """You are an AI agent collecting feedback about medical visits.
        Be professional, empathetic, and thorough in collecting feedback.""",
        'greeting': 'Hello, I am calling to collect feedback about your recent medical visit.',
        'farewell': 'Thank you for providing your valuable feedback. Have a great day!',
        'conversation_flow': {
            'greeting': {
                'message': 'I would like to ask you a few questions about your recent visit.',
                'next': 'confirm_visit'
            },
            'confirm_visit': {
                'message': 'Can you confirm you recently visited our medical facility?',
                'next': 'rate_experience'
            },
            'rate_experience': {
                'message': 'On a scale of 1 to 5, with 5 being excellent, how would you rate your overall experience?',
                'next': 'service_quality'
            },
            'service_quality': {
                'message': 'Again on a scale of 1 to 5, how satisfied were you with the medical service provided?',
                'next': 'improvement'
            },
            'improvement': {
                'message': 'Is there anything specific we could improve about our service?',
                'next': 'completion'
            },
            'completion': {
                'message': 'Thank you for your feedback. This will help us improve our services.',
                'next': None
            }
        }
    }
}

# VideoSDK Gateway Configuration
GATEWAY_CONFIG = {
    'verification': {
        'name': 'ID Verification Gateway',
        'address': 'sip.yoursipprovider.com',  # Replace with your SIP provider
        'geo_region': 'us001',
        'transport': 'udp',
        'media_encryption': 'dtls',
        'record': True,
        'noise_cancellation': False
    },
    'medical_feedback': {
        'name': 'Medical Feedback Gateway',
        'address': 'sip.yoursipprovider.com',  # Replace with your SIP provider
        'geo_region': 'us001',
        'transport': 'udp',
        'media_encryption': 'dtls',
        'record': True,
        'noise_cancellation': False
    }
}

# Example test data
TEST_DATA = {
    'verification': {
        'id': 'ver_123',
        'name': 'John Doe',
        'dob': '01/15/1990',
        'address': '123 Main St, City, State 12345',
        'phone': '+1234567890'
    },
    'medical_feedback': {
        'visit_id': 'visit_123',
        'patient_name': 'Jane Doe',
        'visit_date': '2024-03-15',
        'department': 'Cardiology',
        'phone': '+0987654321'
    }
}
