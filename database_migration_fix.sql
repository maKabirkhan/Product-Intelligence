-- ============================================================================
-- FIX: Update user_id from INTEGER to UUID (for Supabase native auth)
-- ============================================================================
-- Run this in Supabase SQL Editor
-- This modifies existing tables to use auth.users(id) instead of users(user_id)
-- ============================================================================

-- Step 1: Drop existing foreign key constraints
ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS chat_sessions_user_id_fkey;
ALTER TABLE scraping_queries DROP CONSTRAINT IF EXISTS scraping_queries_user_id_fkey;
ALTER TABLE rag_agents DROP CONSTRAINT IF EXISTS rag_agents_user_id_fkey;
ALTER TABLE rag_chat_history DROP CONSTRAINT IF EXISTS rag_chat_history_user_id_fkey;
ALTER TABLE scraping_logs DROP CONSTRAINT IF EXISTS scraping_logs_user_id_fkey;

-- Step 2: Change user_id column type from INTEGER to UUID
ALTER TABLE chat_sessions ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE scraping_queries ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE rag_agents ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE rag_chat_history ALTER COLUMN user_id TYPE UUID USING NULL;
ALTER TABLE scraping_logs ALTER COLUMN user_id TYPE UUID USING NULL;

-- Step 3: Add new foreign key constraints referencing auth.users
ALTER TABLE chat_sessions
    ADD CONSTRAINT chat_sessions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE scraping_queries
    ADD CONSTRAINT scraping_queries_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE rag_agents
    ADD CONSTRAINT rag_agents_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE rag_chat_history
    ADD CONSTRAINT rag_chat_history_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE scraping_logs
    ADD CONSTRAINT scraping_logs_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- Step 4: Enable Row Level Security (RLS)
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraping_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag_agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag_agent_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag_chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraping_logs ENABLE ROW LEVEL SECURITY;

-- Step 5: Create RLS Policies
-- chat_sessions
DROP POLICY IF EXISTS "Users can view own sessions" ON chat_sessions;
DROP POLICY IF EXISTS "Users can insert own sessions" ON chat_sessions;
DROP POLICY IF EXISTS "Users can update own sessions" ON chat_sessions;
DROP POLICY IF EXISTS "Users can delete own sessions" ON chat_sessions;

CREATE POLICY "Users can view own sessions" ON chat_sessions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own sessions" ON chat_sessions FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own sessions" ON chat_sessions FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own sessions" ON chat_sessions FOR DELETE USING (auth.uid() = user_id);

-- scraping_queries
DROP POLICY IF EXISTS "Users can view own queries" ON scraping_queries;
DROP POLICY IF EXISTS "Users can insert own queries" ON scraping_queries;
DROP POLICY IF EXISTS "Users can update own queries" ON scraping_queries;
DROP POLICY IF EXISTS "Users can delete own queries" ON scraping_queries;

CREATE POLICY "Users can view own queries" ON scraping_queries FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own queries" ON scraping_queries FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own queries" ON scraping_queries FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own queries" ON scraping_queries FOR DELETE USING (auth.uid() = user_id);

-- rag_agents
DROP POLICY IF EXISTS "Users can view own agents" ON rag_agents;
DROP POLICY IF EXISTS "Users can insert own agents" ON rag_agents;
DROP POLICY IF EXISTS "Users can update own agents" ON rag_agents;
DROP POLICY IF EXISTS "Users can delete own agents" ON rag_agents;

CREATE POLICY "Users can view own agents" ON rag_agents FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own agents" ON rag_agents FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own agents" ON rag_agents FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own agents" ON rag_agents FOR DELETE USING (auth.uid() = user_id);

-- rag_chat_history
DROP POLICY IF EXISTS "Users can view own chat history" ON rag_chat_history;
DROP POLICY IF EXISTS "Users can insert own chat history" ON rag_chat_history;
DROP POLICY IF EXISTS "Users can delete own chat history" ON rag_chat_history;

CREATE POLICY "Users can view own chat history" ON rag_chat_history FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own chat history" ON rag_chat_history FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can delete own chat history" ON rag_chat_history FOR DELETE USING (auth.uid() = user_id);

-- scraping_logs
DROP POLICY IF EXISTS "Users can view own logs" ON scraping_logs;
DROP POLICY IF EXISTS "Users can insert own logs" ON scraping_logs;

CREATE POLICY "Users can view own logs" ON scraping_logs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own logs" ON scraping_logs FOR INSERT WITH CHECK (auth.uid() = user_id);

-- ============================================================================
-- DONE! user_id is now UUID referencing auth.users(id)
-- ============================================================================
