import os

# API Configuration
VIDEO_SDK_TOKEN = os.getenv('VIDEO_SDK_TOKEN', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlrZXkiOiI0ZjU1MWI1Yy1mYmEyLTQ0OWQtYjU5NC02MjNhYzgyMGIwZWYiLCJwZXJtaXNzaW9ucyI6WyJhbGxvd19qb2luIl0sImlhdCI6MTc1NTg1MDIyNCwiZXhwIjoxNzU2NDU1MDI0fQ.QfQRnX2Xq2ozv2nblTMsQ3luc9Ad7CaY0VXHd5hIVRo')

# Gateway Configuration
GATEWAY_CONFIG = {
    'name': 'ID Verification Gateway',
    'address': 'videosdk.pstn.twilio.com',  # Replace with your SIP provider
}

# Verification Flow Configuration
VERIFICATION_STEPS = {
    'greeting': {
        'message': 'Hello, this is the verification system calling. We need to verify your identity.',
        'next': 'confirm_identity'
    },
    'confirm_identity': {
        'message': 'Please confirm your full name.',
        'next': 'verify_dob'
    },
    'verify_dob': {
        'message': 'Please state your date of birth.',
        'next': 'verify_address'
    },
    'verify_address': {
        'message': 'Please confirm your current address.',
        'next': 'completion'
    },
    'completion': {
        'message': 'Thank you for verifying your identity. Your verification is complete.',
        'next': None
    }
}
