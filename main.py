import asyncio
import os
from dotenv import load_dotenv
from id_verification.src.verification_agent import IDVerificationAgent
from medical_feedback.src.feedback_agent import MedicalFeedbackAgent
from pipeline_setup import PipelineManager
from videosdk.agents import AgentSession, WorkerJob

# Load environment variables
load_dotenv()

async def start_verification_agent(auth_token: str, verification_data: dict):
    """Start an ID verification agent session"""
    agent = IDVerificationAgent()
    
    # Set up the pipeline
    pipeline = await PipelineManager.create_pipeline(voice="Leda")
    
    # Create a unique room for this verification
    room_id = f"verify_{verification_data['id']}"
    
    # Create job context
    context = PipelineManager.create_job_context(
        room_id=room_id,
        auth_token=auth_token,
        agent_name="ID Verification Assistant"
    )
    
    # Create the agent session
    session = AgentSession(
        agent=agent,
        pipeline=pipeline
    )
    
    try:
        # Connect to the room
        await context.connect()
        
        # Start the verification process
        await agent.start_verification(
            to_number=verification_data['phone'],
            from_number=os.getenv('OUTBOUND_NUMBER'),
            verification_data=verification_data
        )
        
        # Start the session
        await session.start()
        
        # Keep the session running
        await asyncio.Event().wait()
    finally:
        await session.close()
        await context.shutdown()

async def start_medical_feedback_agent(auth_token: str, visit_data: dict):
    """Start a medical feedback agent session"""
    agent = MedicalFeedbackAgent()
    
    # Set up the pipeline
    pipeline = await PipelineManager.create_pipeline(voice="Charon")
    
    # Create a unique room for this feedback session
    room_id = f"feedback_{visit_data['visit_id']}"
    
    # Create job context
    context = PipelineManager.create_job_context(
        room_id=room_id,
        auth_token=auth_token,
        agent_name="Medical Feedback Assistant"
    )
    
    # Create the agent session
    session = AgentSession(
        agent=agent,
        pipeline=pipeline
    )
    
    try:
        # Connect to the room
        await context.connect()
        
        # Start the feedback process
        await agent.start_feedback_call(
            to_number=visit_data['phone'],
            from_number=os.getenv('OUTBOUND_NUMBER'),
            visit_data=visit_data
        )
        
        # Start the session
        await session.start()
        
        # Keep the session running
        await asyncio.Event().wait()
    finally:
        await session.close()
        await context.shutdown()

def main():
    # Example verification data
    verification_data = {
        'id': 'ver_123',
        'name': 'John Doe',
        'dob': '1990-01-01',
        'address': '123 Main St, City, State 12345',
        'phone': '+1234567890'
    }
    
    # Example medical visit data
    visit_data = {
        'visit_id': 'visit_123',
        'patient_name': 'Jane Doe',
        'visit_date': '2024-03-15',
        'department': 'Cardiology',
        'phone': '+0987654321'
    }
    
    # Get VideoSDK auth token from environment
    auth_token = os.getenv('VIDEOSDK_AUTH_TOKEN')
    if not auth_token:
        raise ValueError("VIDEOSDK_AUTH_TOKEN not found in environment")
    
    # Create and start the verification job
    ver_job = WorkerJob(
        entrypoint=lambda ctx: start_verification_agent(auth_token, verification_data),
        jobctx=None
    )
    
    # Create and start the medical feedback job
    med_job = WorkerJob(
        entrypoint=lambda ctx: start_medical_feedback_agent(auth_token, visit_data),
        jobctx=None
    )
    
    # Start both jobs
    ver_job.start()
    med_job.start()
    
    try:
        # Keep the main thread running
        while True:
            asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down agents...")
        ver_job.stop()
        med_job.stop()

if __name__ == "__main__":
    main()
