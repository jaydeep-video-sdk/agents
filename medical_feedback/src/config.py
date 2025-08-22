import os

# API Configuration
VIDEO_SDK_TOKEN = os.getenv('VIDEO_SDK_TOKEN', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlrZXkiOiI0ZjU1MWI1Yy1mYmEyLTQ0OWQtYjU5NC02MjNhYzgyMGIwZWYiLCJwZXJtaXNzaW9ucyI6WyJhbGxvd19qb2luIl0sImlhdCI6MTc1NTg1MDIyNCwiZXhwIjoxNzU2NDU1MDI0fQ.QfQRnX2Xq2ozv2nblTMsQ3luc9Ad7CaY0VXHd5hIVRo')

# Gateway Configuration
GATEWAY_CONFIG = {
    'name': 'Medical Feedback Gateway',
    'address': 'videosdk.pstn.twilio.com',  # Replace with your SIP provider
}

# Feedback Flow Configuration
FEEDBACK_STEPS = {
    'greeting': {
        'message': 'Hello, this is the medical feedback system calling about your recent visit.',
        'next': 'confirm_visit'
    },
    'confirm_visit': {
        'message': 'Can you confirm your recent visit to our medical facility?',
        'next': 'rate_experience'
    },
    'rate_experience': {
        'message': 'On a scale of 1 to 5, how would you rate your overall experience?',
        'next': 'service_quality'
    },
    'service_quality': {
        'message': 'How satisfied were you with the quality of medical service provided?',
        'next': 'improvement'
    },
    'improvement': {
        'message': 'Is there anything we could improve about our service?',
        'next': 'completion'
    },
    'completion': {
        'message': 'Thank you for your valuable feedback. This will help us improve our services.',
        'next': None
    }
}
