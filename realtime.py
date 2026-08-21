import json
import asyncio
import os
from fastapi import WebSocket
from redis.asyncio import Redis

# Redis setup (fallback to local if not provided)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = None

try:
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    print(f"Warning: Could not initialize Redis client. Real-time sync may not work. {e}")

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error sending message to a client: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

# Background task to listen to Redis Pub/Sub
async def redis_listener():
    if not redis_client:
        return
    try:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("food_updates")
        print("Subscribed to Redis channel: food_updates")
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                await manager.broadcast(data)
    except Exception as e:
        print(f"Redis listener encountered an error: {e}")

# Helper to publish events to Redis
async def publish_event(event_type: str, payload: dict):
    if redis_client:
        message = json.dumps({"type": event_type, "payload": payload})
        try:
            await redis_client.publish("food_updates", message)
        except Exception as e:
            print(f"Failed to publish event to Redis: {e}")
