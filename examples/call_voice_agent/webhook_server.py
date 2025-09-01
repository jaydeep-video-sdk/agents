import os
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from typing import Dict, Optional
import json

load_dotenv()

app = FastAPI()

# Store active sessions and their webhook IDs
active_sessions: Dict[str, dict] = {}

@app.post("/webhook/call-events")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        event_type = data.get("event")
        room_id = data.get("roomId")
        call_id = data.get("callId", "unknown")
        
        print(f"📞 Received webhook event: {event_type}")
        print(f"   Room ID: {room_id}")
        print(f"   Call ID: {call_id}")
        print(f"   Full data: {json.dumps(data, indent=2)}")
        
        if event_type == "call-started":
            print("📱 Call has started - phone is ringing...")
            
        elif event_type == "call-answered" and room_id in active_sessions:
            print("✅ Call answered! Sending greeting...")
            session_info = active_sessions[room_id]
            if "session" in session_info:
                try:
                    # Wait a moment before greeting to ensure audio is ready
                    await asyncio.sleep(1)
                    await session_info["session"].say("Hello! I'm your AI voice assistant. How can I help you today?")
                    print("🎤 Greeting sent to caller")
                except Exception as e:
                    print(f"❌ Error sending greeting: {str(e)}")
                    
        elif event_type == "call-ended":
            print("📞 Call has ended")
            if room_id in active_sessions:
                print(f"🧹 Cleaning up session for room {room_id}")
                # The main script will handle cleanup
                
        else:
            print(f"ℹ️ Unhandled event type: {event_type}")
            
        return JSONResponse(content={"status": "ok", "message": f"Processed {event_type}"})
        
    except Exception as e:
        print(f"❌ Error processing webhook: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": str(e)}, 
            status_code=500
        )

@app.get("/")
async def health_check():
    return {"status": "ok", "message": "VideoSDK Webhook Server is running"}

@app.get("/sessions")
async def get_active_sessions():
    """Debug endpoint to see active sessions"""
    session_info = {}
    for room_id, session_data in active_sessions.items():
        session_info[room_id] = {
            "webhook_id": session_data.get("webhook_id"),
            "has_session": "session" in session_data
        }
    return {"active_sessions": session_info}

def add_session(room_id: str, session, webhook_id: str):
    """Add a session with its webhook ID"""
    active_sessions[room_id] = {
        "session": session,
        "webhook_id": webhook_id
    }
    print(f"➕ Added session for room {room_id} with webhook {webhook_id}")

def remove_session(room_id: str) -> Optional[str]:
    """Remove a session and return its webhook ID for cleanup"""
    if room_id in active_sessions:
        webhook_id = active_sessions[room_id].get("webhook_id")
        del active_sessions[room_id]
        print(f"➖ Removed session for room {room_id}")
        return webhook_id
    return None

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WEBHOOK_PORT", 8000))
    print(f"🚀 Starting webhook server on port {port}")
    print(f"📡 Webhook endpoint: http://localhost:{port}/webhook/call-events")
    uvicorn.run(app, host="0.0.0.0", port=port)