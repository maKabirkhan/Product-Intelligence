"""
Chat Sessions Router
Handles CRUD operations for chat/research sessions
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from app.db.session_manager import SessionManager
from app.schemas.sessions import (
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatSessionResponse,
    ChatSessionListResponse,
    MessageResponse,
    SessionStatus
)
from app.auth.utils import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize database manager
db = SessionManager()


# ============================================================================
# CHAT SESSIONS ENDPOINTS
# ============================================================================

@router.post("", response_model=ChatSessionResponse, status_code=201)
async def create_session(
    session_data: Optional[ChatSessionCreate] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new chat session.

    Sessions can also be created lazily when the first query is submitted.
    This endpoint allows explicit session creation with an optional title.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    title = session_data.title if session_data else None

    session = db.create_session(user_id=user_id, title=title)
    if not session:
        raise HTTPException(status_code=500, detail="Failed to create session")

    logger.info(f"Created session {session['id']} for user {user_id}")
    return session


@router.get("", response_model=ChatSessionListResponse)
async def list_sessions(
    status: Optional[str] = Query(None, description="Filter by status (active, completed, archived)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    List all chat sessions for the current user.

    - Sessions are ordered by creation date (newest first)
    - Deleted sessions are not returned
    - Use status filter to get only active/completed/archived sessions
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    sessions = db.list_sessions(
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset
    )

    return {
        "sessions": sessions,
        "total": len(sessions)
    }


@router.get("/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific chat session by ID.

    Returns the session details including:
    - Title (auto-generated from queries)
    - Status
    - Total queries count
    - Total products scraped
    - Associated RAG agent ID (if created)
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    session = db.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.patch("/{session_id}", response_model=ChatSessionResponse)
async def update_session(
    session_id: str,
    session_data: ChatSessionUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a chat session.

    Updateable fields:
    - title: Custom session title
    - status: Session status (active, completed, archived)
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    # Verify session exists
    session = db.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build updates
    updates = {}
    if session_data.title is not None:
        updates["title"] = session_data.title
    if session_data.status is not None:
        updates["status"] = session_data.status.value

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    success = db.update_session(session_id=session_id, user_id=user_id, updates=updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update session")

    # Return updated session
    return db.get_session(session_id=session_id, user_id=user_id)


@router.delete("/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a chat session (soft delete).

    - The session is marked as 'deleted' but not removed from database
    - Associated RAG agent is NOT deleted (must be deleted separately)
    - Queries and logs within the session are retained
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    # Verify session exists
    session = db.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    success = db.delete_session(session_id=session_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete session")

    logger.info(f"Deleted session {session_id} for user {user_id}")

    return {
        "message": "Session deleted successfully",
        "success": True
    }


@router.post("/{session_id}/archive", response_model=MessageResponse)
async def archive_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Archive a chat session.

    Archived sessions are hidden from the main list but can be restored.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    session = db.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    success = db.update_session(session_id=session_id, user_id=user_id, updates={"status": "archived"})
    if not success:
        raise HTTPException(status_code=500, detail="Failed to archive session")

    return {
        "message": "Session archived successfully",
        "success": True
    }


@router.post("/{session_id}/restore", response_model=MessageResponse)
async def restore_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Restore an archived or deleted session.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    # Get session (including deleted/archived)
    session = db.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    success = db.update_session(session_id=session_id, user_id=user_id, updates={"status": "active"})
    if not success:
        raise HTTPException(status_code=500, detail="Failed to restore session")

    return {
        "message": "Session restored successfully",
        "success": True
    }
