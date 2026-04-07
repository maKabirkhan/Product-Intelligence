"""
WebSocket Router
Provides real-time log streaming for scraping operations
"""

import json
import asyncio
import logging
from typing import Dict, Set
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.db.session_manager import SessionManager
from app.auth.utils import verify_token_sync

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize database manager
db = SessionManager()

# Store active WebSocket connections: {query_id: set of WebSocket connections}
active_connections: Dict[str, Set[WebSocket]] = {}


class ConnectionManager:
    """Manages WebSocket connections for real-time log streaming"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, query_id: str):
        """Accept a new WebSocket connection for a query"""
        await websocket.accept()
        async with self._lock:
            if query_id not in self.active_connections:
                self.active_connections[query_id] = set()
            self.active_connections[query_id].add(websocket)
        logger.info(f"WebSocket connected for query {query_id}")

    async def disconnect(self, websocket: WebSocket, query_id: str):
        """Remove a WebSocket connection"""
        async with self._lock:
            if query_id in self.active_connections:
                self.active_connections[query_id].discard(websocket)
                if not self.active_connections[query_id]:
                    del self.active_connections[query_id]
        logger.info(f"WebSocket disconnected for query {query_id}")

    async def broadcast_to_query(self, query_id: str, message: dict):
        """Broadcast a message to all connections for a query"""
        if query_id not in self.active_connections:
            return

        # Prepare message with timestamp
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()

        message_json = json.dumps(message)

        # Send to all connections
        dead_connections = set()
        for websocket in self.active_connections.get(query_id, set()):
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                dead_connections.add(websocket)

        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                if query_id in self.active_connections:
                    self.active_connections[query_id] -= dead_connections

    def get_connection_count(self, query_id: str) -> int:
        """Get number of active connections for a query"""
        return len(self.active_connections.get(query_id, set()))


# Global connection manager
manager = ConnectionManager()


def validate_token(token: str) -> dict:
    """Validate JWT token and return user info using Supabase"""
    return verify_token_sync(token)


@router.websocket("/scraping/{query_id}")
async def websocket_scraping_logs(
    websocket: WebSocket,
    query_id: str,
    token: str = Query(...)
):
    """
    WebSocket endpoint for real-time scraping logs.

    Connect to receive live updates during URL collection and scraping.

    Usage:
        ws://localhost:8000/ws/scraping/{query_id}?token={jwt_token}

    Message format (incoming from server):
    {
        "type": "log" | "progress" | "status_change" | "error" | "complete",
        "log_type": "info" | "url_collection" | "scraping" | "ocr" | "ai_analysis" | "error" | "success",
        "message": "Log message text",
        "progress_current": 5,
        "progress_total": 20,
        "metadata": {"asin": "...", "stage": "..."},
        "timestamp": "2024-01-01T00:00:00Z"
    }
    """
    # Validate token
    user = validate_token(token)
    if not user:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = user.get("id")

    # Verify query access
    query = db.get_query(query_id=query_id, user_id=user_id)
    if not query:
        await websocket.close(code=4004, reason="Query not found")
        return

    # Connect
    await manager.connect(websocket, query_id)

    # Send initial state
    await websocket.send_json({
        "type": "connected",
        "query_id": query_id,
        "status": query.get("status"),
        "progress": query.get("scraping_progress"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    # Send recent logs
    recent_logs = db.get_logs(query_id=query_id, user_id=user_id, limit=50)
    if recent_logs:
        await websocket.send_json({
            "type": "history",
            "logs": recent_logs,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    try:
        # Keep connection alive and listen for client messages
        while True:
            try:
                # Wait for client messages (ping/pong or commands)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # 30 second timeout
                )

                # Handle client messages
                try:
                    message = json.loads(data)
                    msg_type = message.get("type")

                    if msg_type == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })

                    elif msg_type == "get_status":
                        # Refresh query status
                        query = db.get_query(query_id=query_id, user_id=user_id)
                        await websocket.send_json({
                            "type": "status",
                            "status": query.get("status") if query else "unknown",
                            "progress": query.get("scraping_progress") if query else None,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })

                    elif msg_type == "get_logs":
                        # Get recent logs
                        since = message.get("since")
                        logs = db.get_logs(
                            query_id=query_id,
                            user_id=user_id,
                            since=datetime.fromisoformat(since) if since else None,
                            limit=message.get("limit", 50)
                        )
                        await websocket.send_json({
                            "type": "logs",
                            "logs": logs,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })

                except json.JSONDecodeError:
                    pass  # Ignore invalid JSON

            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                except:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for query {query_id}: {e}")
    finally:
        await manager.disconnect(websocket, query_id)


# ============================================================================
# HELPER FUNCTIONS FOR BROADCASTING
# ============================================================================

async def broadcast_log(query_id: str, log_type: str, message: str,
                        progress_current: int = None, progress_total: int = None,
                        metadata: dict = None):
    """
    Broadcast a log message to all connected clients for a query.

    Call this from background tasks to send real-time updates.
    """
    await manager.broadcast_to_query(query_id, {
        "type": "log",
        "log_type": log_type,
        "message": message,
        "progress_current": progress_current,
        "progress_total": progress_total,
        "metadata": metadata or {}
    })


async def broadcast_status_change(query_id: str, old_status: str, new_status: str):
    """Broadcast a status change to all connected clients"""
    await manager.broadcast_to_query(query_id, {
        "type": "status_change",
        "old_status": old_status,
        "new_status": new_status
    })


async def broadcast_progress(query_id: str, progress: dict):
    """Broadcast progress update to all connected clients"""
    await manager.broadcast_to_query(query_id, {
        "type": "progress",
        "progress": progress
    })


async def broadcast_complete(query_id: str, total_products: int):
    """Broadcast completion message to all connected clients"""
    await manager.broadcast_to_query(query_id, {
        "type": "complete",
        "message": f"Scraping completed! {total_products} products scraped.",
        "total_products": total_products
    })


async def broadcast_error(query_id: str, error_message: str):
    """Broadcast error message to all connected clients"""
    await manager.broadcast_to_query(query_id, {
        "type": "error",
        "message": error_message
    })


async def broadcast_thinking(query_id: str, thinking_data: dict):
    """Broadcast thinking/reasoning message to all connected clients (Perplexity-style)"""
    await manager.broadcast_to_query(query_id, {
        "type": "thinking",
        **thinking_data
    })


# Export manager for use in other modules
def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager"""
    return manager
