-- ============================================================================
-- PRODUCT INTELLIGENCE SYSTEM - DATABASE MIGRATION
-- ============================================================================
-- This SQL adds NEW tables for the restructured architecture
-- It does NOT modify or delete existing tables (users, products)
-- Run this in Supabase SQL Editor
-- ============================================================================

-- ============================================================================
-- 1. CHAT SESSIONS TABLE
-- ============================================================================
-- Represents a conversation/research session (like Perplexity)
-- Lazy-created on first query
-- ============================================================================
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Session Info
    title VARCHAR(500),  -- Auto-generated from first query, updated as more queries added
    status VARCHAR(50) DEFAULT 'active',
    -- Status: active, completed, archived, deleted

    -- Stats
    total_queries INTEGER DEFAULT 0,
    total_products_scraped INTEGER DEFAULT 0,

    -- RAG agent reference (set when agent is created from this session)
    rag_agent_id UUID,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for chat_sessions
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_status ON chat_sessions(status);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions(created_at DESC);

-- ============================================================================
-- 2. SCRAPING QUERIES TABLE
-- ============================================================================
-- Each search query within a chat session
-- Contains collected URLs and scraped products data in JSONB format
-- ============================================================================
CREATE TABLE IF NOT EXISTS scraping_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Query Info
    query_text VARCHAR(1000) NOT NULL,
    query_topic VARCHAR(255),  -- Extracted topic for agent naming (e.g., "HDD", "Laptop")

    -- URL Collection Phase
    collected_urls JSONB DEFAULT '[]'::jsonb,
    -- Structure: [{"asin": "...", "url": "...", "title": "...", "image_url": "..."}]
    total_urls_collected INTEGER DEFAULT 0,

    -- Collection Configuration
    url_collection_config JSONB DEFAULT '{"max_pages": 5, "collect_all": false}'::jsonb,
    -- Structure: {"max_pages": 5, "limit": 100, "collect_all": false}

    -- Scraped Products Data - ALL products in ONE JSONB field
    products_data JSONB DEFAULT '[]'::jsonb,
    -- Structure: Array of complete product objects with all fields
    total_products_scraped INTEGER DEFAULT 0,

    -- Status
    status VARCHAR(50) DEFAULT 'pending',
    -- Flow: pending -> collecting_urls -> urls_collected -> scraping -> paused -> completed/cancelled/voided/error

    -- Progress Tracking
    scraping_progress JSONB DEFAULT '{}'::jsonb,
    -- Structure: {
    --   "current_index": 5,
    --   "total": 20,
    --   "current_asin": "B07...",
    --   "current_stage": "ocr",  -- details, ocr, ai_analysis
    --   "stages": {"details": 5, "ocr": 3, "ai": 2},
    --   "products_completed": 4,
    --   "products_failed": 0
    -- }

    -- Timing
    url_collection_started_at TIMESTAMP WITH TIME ZONE,
    url_collection_completed_at TIMESTAMP WITH TIME ZONE,
    scraping_started_at TIMESTAMP WITH TIME ZONE,
    scraping_paused_at TIMESTAMP WITH TIME ZONE,
    scraping_completed_at TIMESTAMP WITH TIME ZONE,

    -- Error Tracking
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for scraping_queries
CREATE INDEX IF NOT EXISTS idx_scraping_queries_session_id ON scraping_queries(session_id);
CREATE INDEX IF NOT EXISTS idx_scraping_queries_user_id ON scraping_queries(user_id);
CREATE INDEX IF NOT EXISTS idx_scraping_queries_status ON scraping_queries(status);
CREATE INDEX IF NOT EXISTS idx_scraping_queries_created_at ON scraping_queries(created_at DESC);

-- ============================================================================
-- 3. RAG AGENTS TABLE
-- ============================================================================
-- Chatbot agents created from scraped products
-- Separate from chat sessions - persists even if session is deleted
-- ============================================================================
CREATE TABLE IF NOT EXISTS rag_agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Agent Info
    name VARCHAR(500) NOT NULL,  -- Auto-generated like "HDD/Laptop/Soap"
    description TEXT,

    -- Status
    status VARCHAR(50) DEFAULT 'creating',
    -- Status: creating, ready, error, deleted

    -- Vector Store Reference (for Pinecone/other vector DB)
    vector_store_id VARCHAR(255),
    vector_store_provider VARCHAR(50) DEFAULT 'pinecone',
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-small',

    -- Products Info
    total_products INTEGER DEFAULT 0,
    query_topics JSONB DEFAULT '[]'::jsonb,  -- ["HDD", "Laptop", "Soap"]

    -- Source session (nullable - session can be deleted while agent persists)
    source_session_id UUID REFERENCES chat_sessions(id) ON DELETE SET NULL,

    -- Products data snapshot (stored here after embeddings created)
    -- This allows deleting scraped data from scraping_queries after RAG is ready
    products_snapshot JSONB DEFAULT '[]'::jsonb,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    embeddings_created_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for rag_agents
CREATE INDEX IF NOT EXISTS idx_rag_agents_user_id ON rag_agents(user_id);
CREATE INDEX IF NOT EXISTS idx_rag_agents_status ON rag_agents(status);
CREATE INDEX IF NOT EXISTS idx_rag_agents_source_session ON rag_agents(source_session_id);

-- ============================================================================
-- 4. RAG AGENT SOURCES TABLE
-- ============================================================================
-- Links RAG agents to their source queries
-- Tracks which queries contributed to which agent
-- ============================================================================
CREATE TABLE IF NOT EXISTS rag_agent_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES rag_agents(id) ON DELETE CASCADE,
    query_id UUID NOT NULL REFERENCES scraping_queries(id) ON DELETE CASCADE,

    -- Stats from this query
    products_count INTEGER DEFAULT 0,
    query_text VARCHAR(1000),
    query_topic VARCHAR(255),

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique constraint
    UNIQUE(agent_id, query_id)
);

-- Indexes for rag_agent_sources
CREATE INDEX IF NOT EXISTS idx_rag_agent_sources_agent_id ON rag_agent_sources(agent_id);
CREATE INDEX IF NOT EXISTS idx_rag_agent_sources_query_id ON rag_agent_sources(query_id);

-- ============================================================================
-- 5. RAG CHAT HISTORY TABLE
-- ============================================================================
-- Conversation history with RAG agents
-- ============================================================================
CREATE TABLE IF NOT EXISTS rag_chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES rag_agents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Message
    role VARCHAR(20) NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,

    -- Metadata (sources, citations, etc.)
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for rag_chat_history
CREATE INDEX IF NOT EXISTS idx_rag_chat_history_agent_id ON rag_chat_history(agent_id);
CREATE INDEX IF NOT EXISTS idx_rag_chat_history_user_id ON rag_chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_rag_chat_history_created_at ON rag_chat_history(created_at);

-- ============================================================================
-- 6. SCRAPING LOGS TABLE
-- ============================================================================
-- Real-time logs for WebSocket "thinking" feature
-- ============================================================================
CREATE TABLE IF NOT EXISTS scraping_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL REFERENCES scraping_queries(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Log Info
    log_type VARCHAR(50) NOT NULL,
    -- Types: info, url_collection, scraping, ocr, ai_analysis, error, warning, success

    message TEXT NOT NULL,

    -- Progress Info (optional)
    progress_current INTEGER,
    progress_total INTEGER,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    -- Structure: {"asin": "...", "url": "...", "stage": "...", "duration_ms": 1234}

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for scraping_logs
CREATE INDEX IF NOT EXISTS idx_scraping_logs_query_id ON scraping_logs(query_id);
CREATE INDEX IF NOT EXISTS idx_scraping_logs_user_id ON scraping_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_scraping_logs_created_at ON scraping_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraping_logs_type ON scraping_logs(log_type);

-- ============================================================================
-- 7. TRIGGER FUNCTION FOR updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to new tables
DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON chat_sessions;
CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_scraping_queries_updated_at ON scraping_queries;
CREATE TRIGGER update_scraping_queries_updated_at
    BEFORE UPDATE ON scraping_queries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_rag_agents_updated_at ON rag_agents;
CREATE TRIGGER update_rag_agents_updated_at
    BEFORE UPDATE ON rag_agents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 8. HELPER FUNCTION: Update session stats
-- ============================================================================
CREATE OR REPLACE FUNCTION update_session_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update chat_sessions stats when scraping_queries changes
    UPDATE chat_sessions
    SET
        total_queries = (
            SELECT COUNT(*) FROM scraping_queries
            WHERE session_id = COALESCE(NEW.session_id, OLD.session_id)
            AND status NOT IN ('voided', 'cancelled')
        ),
        total_products_scraped = (
            SELECT COALESCE(SUM(total_products_scraped), 0) FROM scraping_queries
            WHERE session_id = COALESCE(NEW.session_id, OLD.session_id)
            AND status = 'completed'
        )
    WHERE id = COALESCE(NEW.session_id, OLD.session_id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_session_stats ON scraping_queries;
CREATE TRIGGER trigger_update_session_stats
    AFTER INSERT OR UPDATE OR DELETE ON scraping_queries
    FOR EACH ROW
    EXECUTE FUNCTION update_session_stats();

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- New tables created:
-- 1. chat_sessions - Research/conversation sessions
-- 2. scraping_queries - Individual queries with URLs and products data
-- 3. rag_agents - Chatbot agents
-- 4. rag_agent_sources - Query-to-agent links
-- 5. rag_chat_history - Chat history with agents
-- 6. scraping_logs - Real-time logs for WebSocket
--
-- Existing tables (users, products) are NOT modified
-- ============================================================================
