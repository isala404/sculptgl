import modal
import json
import asyncio
from urllib.parse import parse_qs
from pathlib import Path

app = modal.App("websocket-image-server")
app.image = modal.Image.debian_slim().pip_install("fastapi", "websockets", "python-multipart").add_local_dir(
        Path(__file__).parent / "app",
        "/root/app",
        copy=True,
    )
# Store user settings and connections
users = {}

@app.function(max_containers=2)
@modal.concurrent(max_inputs=1000)
@modal.asgi_app()
def endpoint():
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    
    app = FastAPI()
    
    app.mount("/css", StaticFiles(directory="app/css"), name="css")
    app.mount("/resources", StaticFiles(directory="app/resources"), name="resources")
    app.mount("/worker", StaticFiles(directory="app/worker"), name="worker")

    # Serve JS files from app root
    @app.get("/sculptgl.js")
    async def get_js():
        return FileResponse("app/sculptgl.js")

    @app.get("/sculptgl.js.LICENSE.txt")
    async def get_license():
        return FileResponse("app/sculptgl.js.LICENSE.txt")

    # Serve HTML files
    @app.get("/")
    async def root():
        return FileResponse("app/index.html")

    @app.get("/authSuccess.html")
    async def auth_success():
        return FileResponse("app/authSuccess.html")


    @app.websocket("/ws")
    async def websocket_handler(websocket: WebSocket) -> None:
        # Extract user_id from query params
        query_params = dict(websocket.query_params)
        user_id = query_params.get('userid')
        
        if not user_id:
            await websocket.close(code=1000, reason="Missing userid parameter")
            return
        
        await websocket.accept()
        users[user_id] = {'websocket': websocket, 'settings': None}
        
        try:
            while True:
                # Receive message (could be text or bytes)
                message = await websocket.receive()
                
                if 'text' in message and message['text'] is not None:  # JSON settings
                    try:
                        settings = json.loads(message['text'])
                        if all(key in settings for key in ['style', 'strength', 'seed']):
                            users[user_id]['settings'] = settings
                            await websocket.send_json({"status": "settings_saved"})
                        else:
                            await websocket.send_json({"error": "Missing required fields: style, strength, seed"})
                    except json.JSONDecodeError:
                        await websocket.send_json({"error": "Invalid JSON"})
                
                elif 'bytes' in message and message['bytes'] is not None:  # Binary image
                    if users[user_id]['settings'] is None:
                        await websocket.send_json({"error": "Send JSON settings first"})
                    else:
                        # Print user info
                        print(f"User: {user_id}, Settings: {users[user_id]['settings']}")
                        
                        # Wait 1 second and return the same image
                        await asyncio.sleep(1)
                        await websocket.send_bytes(message['bytes'])
        
        except WebSocketDisconnect:
            pass
        finally:
            # Clean up user data
            if user_id in users:
                del users[user_id]
    
    return app
