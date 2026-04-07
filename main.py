#!/usr/bin/env python3
"""
Product Intelligence API - Main Entry Point
Single entry point for the entire backend application
"""

import sys
import asyncio
import os
import logging
from contextlib import asynccontextmanager

# ==============================================================================
# SET WINDOWS PROACTOR POLICY BEFORE ANY IMPORTS
# ==============================================================================
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("Windows Proactor Policy Set")

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Import Routers - Authentication
from app.routers import auth

# Import Routers - New Architecture (Sessions, Queries, Agents)
from app.routers import sessions, queries, agents, websocket

# Import Legacy Router (for backward compatibility)
from app.routers import scraper as legacy_scraper

# Load Environment Variables
load_dotenv()

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("api.log")
    ]
)

logger = logging.getLogger(__name__)


# ==============================================================================
# LIFESPAN EVENT HANDLER
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events"""
    # Startup
    loop = asyncio.get_running_loop()
    loop_name = type(loop).__name__

    logger.info("=" * 60)
    logger.info("PRODUCT INTELLIGENCE API STARTING")
    logger.info("=" * 60)
    logger.info(f"Event Loop: {loop_name}")

    if "Selector" in loop_name and sys.platform == "win32":
        logger.warning("Uvicorn is using Selector loop (subprocesses may have issues)")
        logger.info("Background tasks will use separate Proactor loop")

    logger.info("API is ready to accept requests")
    logger.info("=" * 60)

    yield  # Application runs here

    # Shutdown
    logger.info("Product Intelligence API shutting down...")


# ==============================================================================
# FASTAPI APPLICATION
# ==============================================================================
app = FastAPI(
    title="Product Intelligence API",
    description="""
    Backend API for Product Intelligence System

    ## Features
    - User Authentication (Supabase Native Auth)
    - Chat Sessions (like Perplexity AI)
    - Amazon Product Scraping with real-time progress
    - OCR Processing for product images
    - AI Analysis of products
    - RAG Chatbot Agents

    ## Authentication
    All endpoints (except auth) require a Bearer token in the Authorization header.

    ## Real-time Updates
    Use WebSocket endpoints to receive live scraping progress with "thinking" logs.
    """,
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# ==============================================================================
# CORS MIDDLEWARE
# ==============================================================================
# Configure allowed origins (update for production)
origins = [
    "*",  # Allow all origins for development
    # Add specific origins for production:
    # "http://localhost:3000",
    # "https://yourdomain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# REGISTER ROUTERS
# ==============================================================================

# Authentication Router
app.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

# Chat Sessions Router (New)
app.include_router(
    sessions.router,
    prefix="/api/sessions",
    tags=["Chat Sessions"]
)

# Scraping Queries Router (New)
app.include_router(
    queries.router,
    prefix="/api/sessions",
    tags=["Scraping Queries"]
)

# RAG Agents Router (New)
app.include_router(
    agents.router,
    prefix="/api/agents",
    tags=["RAG Agents"]
)

# WebSocket Router (New)
app.include_router(
    websocket.router,
    prefix="/ws",
    tags=["WebSocket"]
)

# Legacy Scraper Router (for backward compatibility)
app.include_router(
    legacy_scraper.router,
    prefix="/api/scraper",
    tags=["Legacy Scraper (Deprecated)"]
)

# ==============================================================================
# HEALTH CHECK & INFO ENDPOINTS
# ==============================================================================

@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint"""
    return {
        "status": "active",
        "service": "Product Intelligence API",
        "version": "3.0.0"
    }


@app.get("/info", tags=["Health"])
def api_info():
    """API information endpoint"""
    return {
        "name": "Product Intelligence API",
        "version": "3.0.0",
        "description": "Backend for Product Scraping, OCR, AI Analysis & RAG Chatbots",
        "endpoints": {
            "authentication": "/auth",
            "sessions": "/api/sessions",
            "queries": "/api/sessions/{session_id}/queries",
            "agents": "/api/agents",
            "websocket": "/ws/scraping/{query_id}",
            "legacy_scraper": "/api/scraper (deprecated)"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("RELOAD", "false").lower() == "true"

    print()
    print("=" * 60)
    print("  PRODUCT INTELLIGENCE API")
    print("=" * 60)
    print(f"  Server: http://{host}:{port}")
    print(f"  Docs:   http://localhost:{port}/docs")
    print(f"  ReDoc:  http://localhost:{port}/redoc")
    print("=" * 60)
    print()

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload
    )
