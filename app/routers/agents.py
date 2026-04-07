"""
RAG Agents Router
Handles agent creation, management, and chat functionality
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks

from app.db.session_manager import SessionManager
from app.schemas.sessions import (
    RagAgentCreate,
    RagAgentResponse,
    RagAgentListResponse,
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    ChatMessage,
    MessageResponse
)
from app.auth.utils import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize database manager
db = SessionManager()


# ============================================================================
# RAG AGENTS ENDPOINTS
# ============================================================================

@router.post("", response_model=RagAgentResponse, status_code=201)
async def create_agent(
    agent_data: RagAgentCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a RAG agent from a session's scraped products.

    Prerequisites:
    - Session must have at least one completed scraping query
    - Products data must be available

    The agent creation process:
    1. Collects all products from completed queries in the session
    2. Creates the agent record
    3. (Future) Creates embeddings in vector store
    4. Updates agent status to 'ready'

    The agent name is auto-generated from query topics (e.g., "HDD/Laptop/Soap")
    unless a custom name is provided.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    session_id = str(agent_data.session_id)

    session = db.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("rag_agent_id"):
        raise HTTPException(
            status_code=400,
            detail="An agent already exists for this session. Delete the existing agent first."
        )

    products = db.get_session_products_data(session_id, user_id)
    if not products:
        raise HTTPException(
            status_code=400,
            detail="No scraped products found. Complete at least one scraping query first."
        )

    topics = db.get_session_query_topics(session_id, user_id)

    if agent_data.name:
        agent_name = agent_data.name
    else:
        agent_name = "/".join(topics) if topics else f"Agent-{session_id[:8]}"

    # Create agent
    agent = db.create_agent(
        user_id=user_id,
        session_id=session_id,
        name=agent_name,
        description=agent_data.description,
        query_topics=topics,
        total_products=len(products)
    )

    if not agent:
        raise HTTPException(status_code=500, detail="Failed to create agent")

    # Start background task to create embeddings
    background_tasks.add_task(
        create_agent_embeddings_task,
        agent_id=agent["id"],
        user_id=user_id,
        products=products
    )

    logger.info(f"Created agent {agent['id']} for session {session_id}")

    return agent


@router.get("", response_model=RagAgentListResponse)
async def list_agents(
    status: Optional[str] = Query(None, description="Filter by status (creating, ready, error)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    List all RAG agents for the current user.

    Agents are ordered by creation date (newest first).
    Deleted agents are not returned.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    agents = db.list_agents(
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset
    )

    return {
        "agents": agents,
        "total": len(agents)
    }


@router.get("/{agent_id}", response_model=RagAgentResponse)
async def get_agent(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get details of a specific RAG agent.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    agent = db.get_agent(agent_id=agent_id, user_id=user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent


@router.delete("/{agent_id}", response_model=MessageResponse)
async def delete_agent(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a RAG agent (soft delete).

    This will:
    - Mark the agent as 'deleted'
    - Remove the agent reference from the source session
    - (Future) Delete embeddings from vector store
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    agent = db.get_agent(agent_id=agent_id, user_id=user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Remove agent reference from session
    source_session_id = agent.get("source_session_id")
    if source_session_id:
        db.update_session(source_session_id, user_id, {"rag_agent_id": None})

    # Delete agent
    success = db.delete_agent(agent_id=agent_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete agent")

    # TODO: Delete embeddings from vector store

    logger.info(f"Deleted agent {agent_id}")

    return {
        "message": "Agent deleted successfully",
        "success": True
    }


# ============================================================================
# RAG CHAT ENDPOINTS
# ============================================================================

@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def chat_with_agent(
    agent_id: str,
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Chat with a RAG agent.

    Sends a message to the agent and receives a response based on
    the scraped products data.

    NOTE: This is a placeholder implementation. Full RAG functionality
    (vector search, LLM integration) will be implemented later.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    agent = db.get_agent(agent_id=agent_id, user_id=user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent.get("status") != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Agent is not ready (status: {agent.get('status')})"
        )

    user_message = chat_request.message

    # Save user message to history
    db.add_chat_message(
        agent_id=agent_id,
        user_id=user_id,
        role="user",
        content=user_message
    )

    # TODO: Implement actual RAG logic
    # 1. Convert user message to embedding
    # 2. Search vector store for relevant products
    # 3. Build context from relevant products
    # 4. Call LLM with context and user message
    # 5. Return response

    # Placeholder response
    products_snapshot = agent.get("products_snapshot", [])
    total_products = len(products_snapshot)

    assistant_response = (
        f"I have information about {total_products} products in my knowledge base. "
        f"Topics covered: {', '.join(agent.get('query_topics', []))}. "
        f"\n\nYour question: \"{user_message}\"\n\n"
        f"[RAG functionality coming soon - this is a placeholder response]"
    )

    # Save assistant message to history
    db.add_chat_message(
        agent_id=agent_id,
        user_id=user_id,
        role="assistant",
        content=assistant_response
    )

    return {
        "agent_id": agent_id,
        "message": {
            "role": "assistant",
            "content": assistant_response,
            "metadata": {
                "total_products": total_products,
                "topics": agent.get("query_topics", [])
            }
        },
        "sources": None  # TODO: Return relevant product sources
    }


@router.get("/{agent_id}/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    agent_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):
    """
    Get chat history with a RAG agent.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    agent = db.get_agent(agent_id=agent_id, user_id=user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    history = db.get_chat_history(agent_id=agent_id, user_id=user_id, limit=limit)

    messages = [
        ChatMessage(
            role=msg["role"],
            content=msg["content"],
            metadata=msg.get("metadata")
        )
        for msg in history
    ]

    return {
        "agent_id": agent_id,
        "messages": messages,
        "total": len(messages)
    }


@router.delete("/{agent_id}/chat/history", response_model=MessageResponse)
async def clear_chat_history(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Clear chat history with a RAG agent.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    agent = db.get_agent(agent_id=agent_id, user_id=user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    success = db.clear_chat_history(agent_id=agent_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear chat history")

    return {
        "message": "Chat history cleared successfully",
        "success": True
    }


@router.get("/{agent_id}/products")
async def get_agent_products(
    agent_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    Get the products data stored in an agent.

    Returns the products snapshot used for RAG.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    agent = db.get_agent(agent_id=agent_id, user_id=user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    products = agent.get("products_snapshot", [])
    total = len(products)

    # Apply pagination
    paginated = products[offset:offset + limit]

    return {
        "agent_id": agent_id,
        "products": paginated,
        "total": total,
        "limit": limit,
        "offset": offset
    }


# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def create_agent_embeddings_task(agent_id: str, user_id: int, products: List[dict]):
    """
    Background task to create embeddings for agent products.

    This is a placeholder - actual implementation will:
    1. Process each product's data
    2. Create text embeddings using OpenAI/other embedding model
    3. Store embeddings in Pinecone/other vector store
    4. Update agent status to 'ready'
    """
    try:
        logger.info(f"Creating embeddings for agent {agent_id} with {len(products)} products")

        # Save products snapshot to agent
        db.save_agent_products_snapshot(agent_id, user_id, products)

        # TODO: Implement actual embedding creation
        # 1. Initialize embedding model (OpenAI text-embedding-3-small)
        # 2. Initialize vector store (Pinecone)
        # 3. For each product:
        #    - Create text representation (title + description + bullets + ingredients + ocr_text)
        #    - Generate embedding
        #    - Store in vector store with metadata (asin, title, etc.)
        # 4. Update agent with vector_store_id

        # For now, just mark as ready after a short delay to simulate processing
        import asyncio
        await asyncio.sleep(2)

        # Update agent status to ready
        db.update_agent(agent_id, user_id, {
            "status": "ready",
            "embeddings_created_at": db._now()
        })

        logger.info(f"Agent {agent_id} is now ready")

    except Exception as e:
        logger.error(f"Failed to create embeddings for agent {agent_id}: {e}", exc_info=True)
        db.update_agent(agent_id, user_id, {
            "status": "error",
            "metadata": {"error": str(e)}
        })
