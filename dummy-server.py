import asyncio
import json
import websockets
from urllib.parse import parse_qs, urlparse

# Store user settings and connections
users = {}

async def handle_client(websocket):
    # Extract user_id from query params
    query = parse_qs(urlparse(websocket.request.path).query)
    user_id = query.get('userid', [None])[0]
    
    if not user_id:
        await websocket.close(code=1000, reason="Missing userid parameter")
        return
    
    users[user_id] = {'websocket': websocket, 'settings': None}
    
    try:
        async for message in websocket:
            if isinstance(message, str):  # JSON settings
                try:
                    settings = json.loads(message)
                    if all(key in settings for key in ['style', 'strength', 'seed']):
                        users[user_id]['settings'] = settings
                        await websocket.send(json.dumps({"status": "settings_saved"}))
                    else:
                        await websocket.send(json.dumps({"error": "Missing required fields: style, strength, seed"}))
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({"error": "Invalid JSON"}))
            
            elif isinstance(message, bytes):  # Binary image
                if users[user_id]['settings'] is None:
                    await websocket.send(json.dumps({"error": "Send JSON settings first"}))
                else:
                    # Print user info
                    print(f"User: {user_id}, Settings: {users[user_id]['settings']}")
                    
                    # Wait 1 second and return the same image
                    await asyncio.sleep(1)
                    await websocket.send(message)
    
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Clean up user data
        if user_id in users:
            del users[user_id]

async def main():
    print("WebSocket server started on ws://localhost:8765")
    print("Connect with: ws://localhost:8765?userid=YOUR_USER_ID")
    
    async with websockets.serve(handle_client, "localhost", 8765):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
