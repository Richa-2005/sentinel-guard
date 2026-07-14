from fastapi import WebSocket
from typing import List

class WebSocketConnectionManager:
    def __init__(self):
        # Holds active, listening frontend socket connection descriptors
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_event(self, event_payload: dict):
        """
        Pushes evaluation dictionaries instantly down the channel to client nodes.
        """
        dead_connections = []
        for connection in tuple(self.active_connections):
            try:
                await connection.send_json(event_payload)
            except Exception:
                dead_connections.append(connection)
        for connection in dead_connections:
            self.disconnect(connection)

# Globally instantiated connection manager instance
ws_manager = WebSocketConnectionManager()
