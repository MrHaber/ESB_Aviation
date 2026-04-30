import asyncio
import websockets
import json
import random
from datetime import datetime

async def handler(websocket):
    print(f"New connection from {websocket.remote_address}")
    try:
        while True:
            message = await websocket.recv()
            print(f"Received: {message}")
            if message == "GET_DATA":
                data = {
                    "value": random.randint(1, 100),
                    "timestamp": datetime.now().isoformat(),
                    "status": "success"
                }
                await websocket.send(json.dumps(data))
            else:
                await websocket.send(json.dumps({"error": "Unknown command"}))
    except websockets.ConnectionClosed:
        print(f"Connection closed from {websocket.remote_address}")

async def main():
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    print("WebSocket server started on ws://0.0.0.0:8765")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())