"""
Authentication Router
Uses Supabase native authentication system
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from app.auth.supabase_client import supabase

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)


# ============================================================================
# SCHEMAS
# ============================================================================

class SignUpRequest(BaseModel):
    """Sign up request schema"""
    email: EmailStr
    password: str
    username: Optional[str] = None


class SignInRequest(BaseModel):
    """Sign in request schema"""
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Authentication response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    refresh_token: str


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def sign_up(request: SignUpRequest):
    """
    Register a new user using Supabase native auth.

    The user data is stored in Supabase's auth.users table.
    Additional metadata (username) is stored in user_metadata.
    """
    try:
        # Use Supabase native signup
        response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {
                "data": {
                    "username": request.username or request.email.split("@")[0]
                }
            }
        })

        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sign up failed. Please try again."
            )

        # Check if email confirmation is required
        if response.session is None:
            return {
                "message": "Please check your email to confirm your account",
                "user": {
                    "id": str(response.user.id),
                    "email": response.user.email,
                    "username": response.user.user_metadata.get("username")
                },
                "requires_confirmation": True
            }

        return {
            "message": "User created successfully",
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(response.user.id),
                "email": response.user.email,
                "username": response.user.user_metadata.get("username")
            }
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Sign up error: {error_msg}")

        # Handle common Supabase auth errors
        if "already registered" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sign up failed: {error_msg}"
        )


@router.post("/signin")
async def sign_in(request: SignInRequest):
    """
    Sign in an existing user using Supabase native auth.

    Returns access token, refresh token, and user info.
    """
    try:
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })

        if not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(response.user.id),
                "email": response.user.email,
                "username": response.user.user_metadata.get("username", response.user.email.split("@")[0])
            }
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Sign in error: {error_msg}")

        if "invalid" in error_msg.lower() or "credentials" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


@router.post("/refresh")
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh the access token using a refresh token.
    """
    try:
        response = supabase.auth.refresh_session(request.refresh_token)

        if not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "token_type": "bearer"
        }

    except Exception as e:
        logger.error(f"Refresh token error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token"
        )


@router.post("/signout")
async def sign_out(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Sign out the current user.

    This invalidates the user's session on the server side.
    """
    try:
        # Get user from token to set session
        token = credentials.credentials
        supabase.auth.set_session(token, "")
        supabase.auth.sign_out()

        return {"message": "Successfully signed out"}

    except Exception as e:
        logger.error(f"Sign out error: {str(e)}")
        # Even if there's an error, tell client to clear tokens
        return {"message": "Signed out"}


@router.get("/me")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Get the current authenticated user's information.

    Requires a valid access token in the Authorization header.
    """
    try:
        token = credentials.credentials

        # Get user from Supabase using the token
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
            "username": user.user_metadata.get("username", user.email.split("@")[0]),
            "created_at": user.created_at,
            "email_confirmed": user.email_confirmed_at is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


@router.post("/reset-password")
async def request_password_reset(email: EmailStr):
    """
    Request a password reset email.
    """
    try:
        supabase.auth.reset_password_email(email)
        return {"message": "If an account exists with this email, a reset link has been sent"}

    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        # Don't reveal if email exists or not
        return {"message": "If an account exists with this email, a reset link has been sent"}


# ============================================================================
# HELPER DEPENDENCY
# ============================================================================

async def get_current_user_dependency(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to get current user from token.
    Use this in other routers to protect endpoints.

    Usage:
        @router.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user_dependency)):
            return {"user_id": user["id"]}
    """
    try:
        token = credentials.credentials
        response = supabase.auth.get_user(token)

        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

        return {
            "id": str(response.user.id),
            "email": response.user.email,
            "username": response.user.user_metadata.get("username")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth dependency error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
