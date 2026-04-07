"""
Authentication Utilities
Uses Supabase native authentication for token verification
"""

import os
import logging
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

from app.auth.supabase_client import supabase

load_dotenv()

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Keep SECRET_KEY for WebSocket token validation (backwards compatibility)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Get the current authenticated user from the Supabase access token.

    This is the primary dependency for protecting routes.

    Returns:
        dict: User info with keys: id, email, username

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        token = credentials.credentials
        response = supabase.auth.get_user(token)

        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

        user = response.user
        return {
            "id": str(user.id),
            "email": user.email,
            "username": user.user_metadata.get("username", user.email.split("@")[0])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


def verify_token_sync(token: str) -> dict:
    """
    Synchronous token verification for WebSocket connections.

    Note: This uses Supabase's get_user which validates the JWT.

    Returns:
        dict: User info with keys: id, email, username
        None: If token is invalid
    """
    try:
        response = supabase.auth.get_user(token)

        if not response.user:
            return None

        user = response.user
        return {
            "id": str(user.id),
            "email": user.email,
            "username": user.user_metadata.get("username", user.email.split("@")[0])
        }

    except Exception as e:
        logger.error(f"Sync token verification error: {str(e)}")
        return None


# Legacy functions kept for backwards compatibility during migration
def verify_token(token: str) -> dict:
    """
    Legacy function - use verify_token_sync instead.
    Kept for backwards compatibility.
    """
    return verify_token_sync(token)
