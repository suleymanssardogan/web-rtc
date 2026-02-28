import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import os
import uvicorn
import json

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc-signaling")

# Store active websocket connections
# one broadcaster, many viewers
STATE = {
    "broadcaster": None,
    "viewers": set()
}

@app.get("/")
async def get():
    if os.path.exists("index.html"):
        with open("index.html") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("index.html not found", status_code=404)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_type = None

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")
            
            if msg_type == "register_broadcaster":
                if STATE["broadcaster"] is not None and STATE["broadcaster"] != websocket:
                    logger.warning("Replacing existing broadcaster")
                    # Optionally notify old broadcaster
                
                STATE["broadcaster"] = websocket
                client_type = "broadcaster"
                logger.info("Broadcaster registered")

                # Notify the newly registered broadcaster about all currently waiting viewers
                for viewer in STATE["viewers"]:
                    await websocket.send_text(json.dumps({
                        "type": "new_viewer",
                        "viewer_id": id(viewer)
                    }))

            elif msg_type == "register_viewer":
                STATE["viewers"].add(websocket)
                client_type = "viewer"
                logger.info("Viewer registered")
                
                # Notify broadcaster that a new viewer wants to connect
                if STATE["broadcaster"]:
                    await STATE["broadcaster"].send_text(json.dumps({
                        "type": "new_viewer",
                        "viewer_id": id(websocket)
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Broadcaster is not online"
                    }))

            elif msg_type == "offer":
                target_id = message.get("target_id")
                # Forward offer to the specific viewer
                for v in STATE["viewers"]:
                    if id(v) == target_id:
                        msg = {"type": "offer", "sdp": message["sdp"], "broadcaster_id": id(STATE["broadcaster"])}
                        await v.send_text(json.dumps(msg))
                        break

            elif msg_type == "answer":
                # Viewer answers, forward to broadcaster
                if STATE["broadcaster"]:
                    msg = {"type": "answer", "sdp": message["sdp"], "viewer_id": id(websocket)}
                    await STATE["broadcaster"].send_text(json.dumps(msg))

            elif msg_type == "candidate":
                target = message.get("target")
                if target == "broadcaster" and STATE["broadcaster"]:
                    msg = {"type": "candidate", "candidate": message["candidate"], "viewer_id": id(websocket)}
                    await STATE["broadcaster"].send_text(json.dumps(msg))
                elif target == "viewer":
                    target_id = message.get("target_id")
                    for v in STATE["viewers"]:
                        if id(v) == target_id:
                            msg = {"type": "candidate", "candidate": message["candidate"]}
                            await v.send_text(json.dumps(msg))
                            break

    except WebSocketDisconnect:
        if client_type == "broadcaster":
            STATE["broadcaster"] = None
            logger.info("Broadcaster disconnected")
            for v in STATE["viewers"]:
                await v.send_text(json.dumps({"type": "broadcaster_disconnected"}))
        elif client_type == "viewer":
            STATE["viewers"].discard(websocket)
            logger.info("Viewer disconnected")
            if STATE["broadcaster"]:
                 await STATE["broadcaster"].send_text(json.dumps({
                     "type": "viewer_disconnected",
                     "viewer_id": id(websocket)
                 }))

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
    print(f"Starting WebRTC Signaling Server on port {port}...")
    
    if "PORT" in os.environ:
        print("Production environment detected (ignoring local SSL certs).")
        uvicorn.run(app, host="0.0.0.0", port=port)
    elif os.path.exists("cert.pem") and os.path.exists("key.pem"):
        print(f"Access via: https://{IP}:{port}")
        uvicorn.run(app, host="0.0.0.0", port=port, ssl_keyfile="key.pem", ssl_certfile="cert.pem")
    else:
        print(f"Access via: http://{IP}:{port}")
        print("Warning: WebRTC requires HTTPS unless accessed via localhost!")
        uvicorn.run(app, host="0.0.0.0", port=port)
