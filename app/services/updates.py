import asyncio
import json
from typing import List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        message_json = json.dumps(message)
        # Create a copy of the list to avoid issues with removal during iteration
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message_json)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

async def notify_sale(tier: str, user_name: str, city: str = "London"):
    """Notify all clients of a new sale."""
    await manager.broadcast({
        "type": "sale",
        "tier": tier,
        "user_name": user_name,
        "city": city,
        "timestamp": asyncio.get_event_loop().time()
    })

async def notify_scarcity_update(availability: dict):
    """Notify all clients of updated availability."""
    await manager.broadcast({
        "type": "scarcity",
        "availability": availability
    })
