from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.updates import manager
from app.services import founders_pass

router = APIRouter(prefix="/ws", tags=["updates"])

@router.websocket("/founders-pass")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial availability
        availability = founders_pass.get_availability()
        await websocket.send_json({
            "type": "scarcity",
            "availability": availability
        })
        
        while True:
            # Keep connection open, wait for messages (though we don't expect any from client)
            data = await websocket.receive_text()
            # If client sends something, we can handle it if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
