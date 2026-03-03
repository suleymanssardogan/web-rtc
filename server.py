import logging
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
from livekit.api import AccessToken, VideoGrants

from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# LiveKit connection details (In production, load these from secure environment variables)
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET")

@app.get("/")
async def get():
    if os.path.exists("index.html"):
        with open("index.html") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("index.html not found", status_code=404)

@app.get("/token")
async def get_token(role: str):
    # Generate a random identity for the user connected
    identity = f"{role}_{os.urandom(4).hex()}"
    
    # Create an access token granting permission to join a room
    grant = VideoGrants(room_join=True, room="stream-room")
    
    access_token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity(identity) \
        .with_name(f"{role} user") \
        .with_grants(grant)
        
    # Get the LiveKit Server URL from environment variable, default to local if not set
    livekit_url = os.environ.get("LIVEKIT_URL")
        
    return {
        "token": access_token.to_jwt(),
        "url": livekit_url
    }

if __name__ == "__main__":
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting WebRTC Server on port {port}...")
    
    if "PORT" in os.environ:
        print("Production environment detected (ignoring local SSL certs).")
        uvicorn.run(app, host="0.0.0.0", port=port)
    elif os.path.exists("cert.pem") and os.path.exists("key.pem"):
        print(f"Access via: https://{IP}:{port}")
        uvicorn.run(app, host="0.0.0.0", port=port, ssl_keyfile="key.pem", ssl_certfile="cert.pem")
    else:
        print(f"Access via: http://{IP}:{port}")
        uvicorn.run(app, host="0.0.0.0", port=port)
