"""
Pydantic schemas for Chat Sessions, Scraping Queries, and RAG Agents
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


# ============================================================================
# ENUMS
# ============================================================================

class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    DELETED = "deleted"


class QueryStatus(str, Enum):
    PENDING = "pending"
    COLLECTING_URLS = "collecting_urls"
    URLS_COLLECTED = "urls_collected"
    SCRAPING = "scraping"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    VOIDED = "voided"
    ERROR = "error"


class AgentStatus(str, Enum):
    CREATING = "creating"
    READY = "ready"
    ERROR = "error"
    DELETED = "deleted"


class LogType(str, Enum):
    INFO = "info"
    URL_COLLECTION = "url_collection"
    SCRAPING = "scraping"
    OCR = "ocr"
    AI_ANALYSIS = "ai_analysis"
    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"


# ============================================================================
# COLLECTED URL SCHEMA
# ============================================================================

class CollectedUrl(BaseModel):
    """Schema for a collected product URL"""
    asin: str
    url: str
    title: Optional[str] = None
    image_url: Optional[str] = None


# ============================================================================
# PRODUCT DATA SCHEMA
# ============================================================================

class ProductData(BaseModel):
    """Schema for complete scraped product data"""
    asin: str
    title: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[str] = None
    rating: Optional[str] = None
    reviews: Optional[str] = None
    product_url: Optional[str] = None
    image_url: Optional[str] = None
    image_urls: List[str] = []
    description: Optional[str] = None
    bullet_points: List[str] = []
    availability: Optional[str] = None
    category: Optional[str] = None
    ingredients: Optional[str] = None

    # OCR fields
    ocr_text: Optional[str] = None
    ocr_status: Optional[str] = None

    # AI Analysis fields
    ai_analysis: Optional[Dict[str, Any]] = None

    # Timestamps
    scraped_at: Optional[datetime] = None


# ============================================================================
# URL COLLECTION CONFIG
# ============================================================================

class UrlCollectionConfig(BaseModel):
    """Configuration for URL collection phase"""
    max_pages: int = Field(default=5, ge=1, le=50, description="Maximum pages to scrape")
    limit: Optional[int] = Field(default=None, ge=1, le=500, description="Maximum URLs to collect")
    collect_all: bool = Field(default=False, description="Collect from all pages regardless of limit")


# ============================================================================
# SCRAPING PROGRESS SCHEMA
# ============================================================================

class ScrapingProgress(BaseModel):
    """Schema for tracking scraping progress"""
    current_index: int = 0
    total: int = 0
    current_asin: Optional[str] = None
    current_stage: Optional[str] = None  # details, ocr, ai_analysis
    stages: Dict[str, int] = Field(default_factory=lambda: {"details": 0, "ocr": 0, "ai": 0})
    products_completed: int = 0
    products_failed: int = 0
    started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None


# ============================================================================
# CHAT SESSION SCHEMAS
# ============================================================================

class ChatSessionCreate(BaseModel):
    """Schema for creating a new chat session (optional - can be lazy created)"""
    title: Optional[str] = Field(None, max_length=500)


class ChatSessionUpdate(BaseModel):
    """Schema for updating a chat session"""
    title: Optional[str] = Field(None, max_length=500)
    status: Optional[SessionStatus] = None


class ChatSessionResponse(BaseModel):
    """Response schema for a chat session"""
    id: UUID
    user_id: str
    title: Optional[str]
    status: str
    total_queries: int
    total_products_scraped: int
    rag_agent_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatSessionListResponse(BaseModel):
    """Response schema for listing chat sessions"""
    sessions: List[ChatSessionResponse]
    total: int


# ============================================================================
# SCRAPING QUERY SCHEMAS
# ============================================================================

class ScrapingQueryCreate(BaseModel):
    """Schema for creating a new scraping query"""
    query_text: str = Field(..., min_length=1, max_length=1000)
    url_collection_config: Optional[UrlCollectionConfig] = None

    @field_validator('query_text')
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Query cannot be empty or only whitespace')
        return v.strip()


class ScrapingQueryResponse(BaseModel):
    """Response schema for a scraping query"""
    id: UUID
    session_id: UUID
    user_id: str
    query_text: str
    query_topic: Optional[str]

    # URL Collection
    collected_urls: List[CollectedUrl]
    total_urls_collected: int
    url_collection_config: Optional[Dict[str, Any]]

    # Products Data
    products_data: List[Dict[str, Any]]
    total_products_scraped: int

    # Status & Progress
    status: str
    scraping_progress: Optional[Dict[str, Any]]

    # Timing
    url_collection_started_at: Optional[datetime]
    url_collection_completed_at: Optional[datetime]
    scraping_started_at: Optional[datetime]
    scraping_completed_at: Optional[datetime]

    # Error
    error_message: Optional[str]

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScrapingQueryListResponse(BaseModel):
    """Response schema for listing scraping queries"""
    queries: List[ScrapingQueryResponse]
    total: int


class ScrapingQueryUrlsResponse(BaseModel):
    """Response schema for collected URLs only"""
    query_id: UUID
    query_text: str
    status: str
    collected_urls: List[CollectedUrl]
    total_urls_collected: int
    url_collection_config: Optional[Dict[str, Any]]


# ============================================================================
# SCRAPING CONTROL SCHEMAS
# ============================================================================

class StartScrapingRequest(BaseModel):
    """Request to start scraping collected URLs"""
    # Optional overrides
    max_products: Optional[int] = Field(None, ge=1, le=500, description="Limit products to scrape")
    skip_ocr: bool = Field(default=False, description="Skip OCR processing")
    skip_ai_analysis: bool = Field(default=False, description="Skip AI analysis")


class ScrapingControlResponse(BaseModel):
    """Response for scraping control actions"""
    query_id: UUID
    status: str
    message: str
    progress: Optional[ScrapingProgress] = None


# ============================================================================
# RAG AGENT SCHEMAS
# ============================================================================

class RagAgentCreate(BaseModel):
    """Schema for creating a RAG agent from a session"""
    session_id: UUID
    name: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None


class RagAgentResponse(BaseModel):
    """Response schema for a RAG agent"""
    id: UUID
    user_id: str
    name: str
    description: Optional[str]
    status: str
    vector_store_id: Optional[str]
    vector_store_provider: Optional[str]
    total_products: int
    query_topics: List[str]
    source_session_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    embeddings_created_at: Optional[datetime]

    class Config:
        from_attributes = True


class RagAgentListResponse(BaseModel):
    """Response schema for listing RAG agents"""
    agents: List[RagAgentResponse]
    total: int


# ============================================================================
# RAG CHAT SCHEMAS
# ============================================================================

class ChatMessage(BaseModel):
    """Schema for a chat message"""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """Request to chat with a RAG agent"""
    message: str = Field(..., min_length=1, max_length=10000)


class ChatResponse(BaseModel):
    """Response from RAG agent chat"""
    agent_id: UUID
    message: ChatMessage
    sources: Optional[List[Dict[str, Any]]] = None  # Product references used


class ChatHistoryResponse(BaseModel):
    """Response for chat history"""
    agent_id: UUID
    messages: List[ChatMessage]
    total: int


# ============================================================================
# WEBSOCKET MESSAGE SCHEMAS
# ============================================================================

class WebSocketLogMessage(BaseModel):
    """Schema for WebSocket log messages"""
    type: str  # log, progress, status_change, error, complete
    log_type: Optional[str] = None  # info, url_collection, scraping, ocr, ai_analysis
    message: str
    progress_current: Optional[int] = None
    progress_total: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WebSocketStatusMessage(BaseModel):
    """Schema for WebSocket status updates"""
    type: str = "status_change"
    query_id: UUID
    old_status: str
    new_status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# GENERIC RESPONSE SCHEMAS
# ============================================================================

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str
    detail: Optional[str] = None
    success: bool = False
