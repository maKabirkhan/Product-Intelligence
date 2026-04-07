"""
Database Manager for Chat Sessions, Scraping Queries, and RAG Agents
Handles all database operations for the new architecture
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from uuid import UUID
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class SessionManager:
    """Manages chat sessions, scraping queries, and related operations"""

    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        # Use service role key for backend operations (bypasses RLS)
        self.key = os.getenv("SECRET_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        if not self.url or not self.key:
            raise ValueError("Missing Supabase credentials")
        self.client: Client = create_client(self.url, self.key)
        logger.info("✅ Supabase Manager initialized")

    def _now(self) -> str:
        """Get current UTC timestamp as ISO string"""
        return datetime.now(timezone.utc).isoformat()

    def _serialize_uuid(self, obj: Any) -> Any:
        """Convert UUID to string for JSON serialization"""
        if isinstance(obj, UUID):
            return str(obj)
        return obj

    # =========================================================================
    # CHAT SESSIONS
    # =========================================================================

    def create_session(self, user_id: str, title: Optional[str] = None) -> Optional[Dict]:
        """Create a new chat session"""
        try:
            data = {
                "user_id": user_id,
                "title": title,
                "status": "active",
                "total_queries": 0,
                "total_products_scraped": 0
            }
            response = self.client.table("chat_sessions").insert(data).execute()
            if response.data:
                logger.info(f"Created session {response.data[0]['id']} for user {user_id}")
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return None

    def get_session(self, session_id: str, user_id: str) -> Optional[Dict]:
        """Get a session by ID (with user validation)"""
        try:
            response = self.client.table("chat_sessions") \
                .select("*") \
                .eq("id", session_id) \
                .eq("user_id", user_id) \
                .single() \
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    def list_sessions(self, user_id: str, status: Optional[str] = None,
                      limit: int = 50, offset: int = 0) -> List[Dict]:
        """List all sessions for a user"""
        try:
            query = self.client.table("chat_sessions") \
                .select("*") \
                .eq("user_id", user_id) \
                .neq("status", "deleted") \
                .order("created_at", desc=True) \
                .limit(limit) \
                .offset(offset)

            if status:
                query = query.eq("status", status)

            response = query.execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    def update_session(self, session_id: str, user_id: str, updates: Dict) -> bool:
        """Update a session"""
        try:
            updates["updated_at"] = self._now()
            self.client.table("chat_sessions") \
                .update(updates) \
                .eq("id", session_id) \
                .eq("user_id", user_id) \
                .execute()
            logger.info(f"Updated session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            return False

    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Soft delete a session (set status to deleted)"""
        return self.update_session(session_id, user_id, {"status": "deleted"})

    def update_session_title_from_query(self, session_id: str, user_id: str,
                                        query_text: str, is_first_query: bool) -> bool:
        """Update session title based on query (auto-generate)"""
        try:
            session = self.get_session(session_id, user_id)
            if not session:
                return False

            # Extract topic from query (first few meaningful words)
            topic = self._extract_topic(query_text)

            if is_first_query or not session.get("title"):
                # First query - set title directly
                new_title = topic
            else:
                # Append to existing title
                current_title = session.get("title", "")
                if topic not in current_title:
                    new_title = f"{current_title}/{topic}" if current_title else topic
                else:
                    new_title = current_title

            return self.update_session(session_id, user_id, {"title": new_title[:500]})
        except Exception as e:
            logger.error(f"Failed to update session title: {e}")
            return False

    def _extract_topic(self, query_text: str) -> str:
        """Extract a topic/keyword from query text"""
        # Simple extraction - take first 2-3 meaningful words
        words = query_text.strip().split()
        stop_words = {'the', 'a', 'an', 'for', 'and', 'or', 'best', 'top', 'buy', 'cheap', 'good'}
        meaningful = [w for w in words if w.lower() not in stop_words][:3]
        return " ".join(meaningful).title() if meaningful else query_text[:50]

    # =========================================================================
    # SCRAPING QUERIES
    # =========================================================================

    def create_query(self, session_id: str, user_id: str, query_text: str,
                     url_collection_config: Optional[Dict] = None) -> Optional[Dict]:
        """Create a new scraping query"""
        try:
            # Extract topic
            topic = self._extract_topic(query_text)

            data = {
                "session_id": session_id,
                "user_id": user_id,
                "query_text": query_text,
                "query_topic": topic,
                "status": "pending",
                "collected_urls": [],
                "total_urls_collected": 0,
                "url_collection_config": url_collection_config or {"max_pages": 5, "collect_all": False},
                "products_data": [],
                "total_products_scraped": 0,
                "scraping_progress": {}
            }

            response = self.client.table("scraping_queries").insert(data).execute()
            if response.data:
                query_id = response.data[0]['id']
                logger.info(f"Created query {query_id} for session {session_id}")

                # Check if this is the first query and update session title
                queries = self.list_queries(session_id, user_id, limit=2)
                is_first = len(queries) == 1
                self.update_session_title_from_query(session_id, user_id, query_text, is_first)

                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to create query: {e}")
            return None

    def get_query(self, query_id: str, user_id: str) -> Optional[Dict]:
        """Get a query by ID"""
        try:
            response = self.client.table("scraping_queries") \
                .select("*") \
                .eq("id", query_id) \
                .eq("user_id", user_id) \
                .single() \
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to get query {query_id}: {e}")
            return None

    def list_queries(self, session_id: str, user_id: str,
                     limit: int = 50, offset: int = 0) -> List[Dict]:
        """List all queries for a session"""
        try:
            response = self.client.table("scraping_queries") \
                .select("*") \
                .eq("session_id", session_id) \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .offset(offset) \
                .execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to list queries: {e}")
            return []

    def update_query(self, query_id: str, user_id: str, updates: Dict) -> bool:
        """Update a query"""
        try:
            updates["updated_at"] = self._now()

            # Ensure JSONB fields are properly formatted
            for field in ['collected_urls', 'products_data', 'scraping_progress', 'url_collection_config']:
                if field in updates and updates[field] is not None:
                    if not isinstance(updates[field], (list, dict)):
                        updates[field] = json.loads(updates[field]) if isinstance(updates[field], str) else updates[field]

            self.client.table("scraping_queries") \
                .update(updates) \
                .eq("id", query_id) \
                .eq("user_id", user_id) \
                .execute()
            logger.info(f"Updated query {query_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update query {query_id}: {e}")
            return False

    def update_query_status(self, query_id: str, user_id: str, status: str,
                            error_message: Optional[str] = None) -> bool:
        """Update query status with optional error message"""
        updates = {"status": status}
        if error_message:
            updates["error_message"] = error_message

        # Set timing fields based on status
        now = self._now()
        if status == "collecting_urls":
            updates["url_collection_started_at"] = now
        elif status == "urls_collected":
            updates["url_collection_completed_at"] = now
        elif status == "scraping":
            updates["scraping_started_at"] = now
        elif status == "paused":
            updates["scraping_paused_at"] = now
        elif status in ["completed", "cancelled", "voided"]:
            updates["scraping_completed_at"] = now

        return self.update_query(query_id, user_id, updates)

    def save_collected_urls(self, query_id: str, user_id: str,
                            urls: List[Dict]) -> bool:
        """Save collected URLs to a query"""
        try:
            updates = {
                "collected_urls": urls,
                "total_urls_collected": len(urls),
                "status": "urls_collected",
                "url_collection_completed_at": self._now()
            }
            return self.update_query(query_id, user_id, updates)
        except Exception as e:
            logger.error(f"Failed to save URLs for query {query_id}: {e}")
            return False

    def add_product_data(self, query_id: str, user_id: str,
                         product: Dict) -> bool:
        """Add a single product's data to the query"""
        try:
            query = self.get_query(query_id, user_id)
            if not query:
                return False

            products = query.get("products_data", []) or []
            products.append(product)

            updates = {
                "products_data": products,
                "total_products_scraped": len(products)
            }
            return self.update_query(query_id, user_id, updates)
        except Exception as e:
            logger.error(f"Failed to add product data: {e}")
            return False

    def update_product_in_query(self, query_id: str, user_id: str,
                                asin: str, product_updates: Dict) -> bool:
        """Update a specific product within a query's products_data"""
        try:
            query = self.get_query(query_id, user_id)
            if not query:
                return False

            products = query.get("products_data", []) or []

            # Find and update the product
            for i, product in enumerate(products):
                if product.get("asin") == asin:
                    products[i].update(product_updates)
                    break

            return self.update_query(query_id, user_id, {"products_data": products})
        except Exception as e:
            logger.error(f"Failed to update product {asin}: {e}")
            return False

    def update_scraping_progress(self, query_id: str, user_id: str,
                                  progress: Dict) -> bool:
        """Update scraping progress"""
        return self.update_query(query_id, user_id, {"scraping_progress": progress})

    def void_query(self, query_id: str, user_id: str) -> bool:
        """Mark a query as voided (user started new query without scraping)"""
        return self.update_query_status(query_id, user_id, "voided")

    # =========================================================================
    # SCRAPING LOGS
    # =========================================================================

    def add_log(self, query_id: str, user_id: str, log_type: str, message: str,
                progress_current: Optional[int] = None, progress_total: Optional[int] = None,
                metadata: Optional[Dict] = None) -> Optional[Dict]:
        """Add a log entry for a query"""
        try:
            data = {
                "query_id": query_id,
                "user_id": user_id,
                "log_type": log_type,
                "message": message,
                "progress_current": progress_current,
                "progress_total": progress_total,
                "metadata": metadata or {}
            }
            response = self.client.table("scraping_logs").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to add log: {e}")
            return None

    def get_logs(self, query_id: str, user_id: str,
                 since: Optional[datetime] = None, limit: int = 100) -> List[Dict]:
        """Get logs for a query"""
        try:
            query = self.client.table("scraping_logs") \
                .select("*") \
                .eq("query_id", query_id) \
                .eq("user_id", user_id) \
                .order("created_at", desc=False) \
                .limit(limit)

            if since:
                query = query.gt("created_at", since.isoformat())

            response = query.execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return []

    # =========================================================================
    # RAG AGENTS
    # =========================================================================

    def create_agent(self, user_id: str, session_id: str, name: str,
                     description: Optional[str] = None,
                     query_topics: Optional[List[str]] = None,
                     total_products: int = 0) -> Optional[Dict]:
        """Create a new RAG agent"""
        try:
            data = {
                "user_id": user_id,
                "name": name,
                "description": description,
                "status": "creating",
                "source_session_id": session_id,
                "query_topics": query_topics or [],
                "total_products": total_products,
                "products_snapshot": []
            }
            response = self.client.table("rag_agents").insert(data).execute()
            if response.data:
                agent_id = response.data[0]['id']
                logger.info(f"Created agent {agent_id} for user {user_id}")

                # Update session with agent reference
                self.update_session(session_id, user_id, {"rag_agent_id": agent_id})

                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            return None

    def get_agent(self, agent_id: str, user_id: str) -> Optional[Dict]:
        """Get an agent by ID"""
        try:
            response = self.client.table("rag_agents") \
                .select("*") \
                .eq("id", agent_id) \
                .eq("user_id", user_id) \
                .single() \
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to get agent {agent_id}: {e}")
            return None

    def list_agents(self, user_id: str, status: Optional[str] = None,
                    limit: int = 50, offset: int = 0) -> List[Dict]:
        """List all agents for a user"""
        try:
            query = self.client.table("rag_agents") \
                .select("*") \
                .eq("user_id", user_id) \
                .neq("status", "deleted") \
                .order("created_at", desc=True) \
                .limit(limit) \
                .offset(offset)

            if status:
                query = query.eq("status", status)

            response = query.execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return []

    def update_agent(self, agent_id: str, user_id: str, updates: Dict) -> bool:
        """Update an agent"""
        try:
            updates["updated_at"] = self._now()
            self.client.table("rag_agents") \
                .update(updates) \
                .eq("id", agent_id) \
                .eq("user_id", user_id) \
                .execute()
            logger.info(f"Updated agent {agent_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update agent {agent_id}: {e}")
            return False

    def delete_agent(self, agent_id: str, user_id: str) -> bool:
        """Soft delete an agent"""
        return self.update_agent(agent_id, user_id, {"status": "deleted"})

    def save_agent_products_snapshot(self, agent_id: str, user_id: str,
                                      products: List[Dict]) -> bool:
        """Save products snapshot to agent (for RAG)"""
        return self.update_agent(agent_id, user_id, {
            "products_snapshot": products,
            "total_products": len(products)
        })

    def add_agent_source(self, agent_id: str, query_id: str,
                         products_count: int, query_text: str,
                         query_topic: Optional[str] = None) -> Optional[Dict]:
        """Link a query as a source for an agent"""
        try:
            data = {
                "agent_id": agent_id,
                "query_id": query_id,
                "products_count": products_count,
                "query_text": query_text,
                "query_topic": query_topic
            }
            response = self.client.table("rag_agent_sources").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to add agent source: {e}")
            return None

    # =========================================================================
    # RAG CHAT HISTORY
    # =========================================================================

    def add_chat_message(self, agent_id: str, user_id: str, role: str,
                         content: str, metadata: Optional[Dict] = None) -> Optional[Dict]:
        """Add a chat message to history"""
        try:
            data = {
                "agent_id": agent_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "metadata": metadata or {}
            }
            response = self.client.table("rag_chat_history").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to add chat message: {e}")
            return None

    def get_chat_history(self, agent_id: str, user_id: str,
                         limit: int = 50) -> List[Dict]:
        """Get chat history for an agent"""
        try:
            response = self.client.table("rag_chat_history") \
                .select("*") \
                .eq("agent_id", agent_id) \
                .eq("user_id", user_id) \
                .order("created_at", desc=False) \
                .limit(limit) \
                .execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get chat history: {e}")
            return []

    def clear_chat_history(self, agent_id: str, user_id: str) -> bool:
        """Clear chat history for an agent"""
        try:
            self.client.table("rag_chat_history") \
                .delete() \
                .eq("agent_id", agent_id) \
                .eq("user_id", user_id) \
                .execute()
            logger.info(f"Cleared chat history for agent {agent_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear chat history: {e}")
            return False

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def get_session_products_data(self, session_id: str, user_id: str) -> List[Dict]:
        """Get all products data from completed queries in a session"""
        try:
            queries = self.client.table("scraping_queries") \
                .select("products_data, query_topic") \
                .eq("session_id", session_id) \
                .eq("user_id", user_id) \
                .eq("status", "completed") \
                .execute()

            all_products = []
            for query in queries.data or []:
                products = query.get("products_data", []) or []
                all_products.extend(products)

            return all_products
        except Exception as e:
            logger.error(f"Failed to get session products: {e}")
            return []

    def get_session_query_topics(self, session_id: str, user_id: str) -> List[str]:
        """Get all query topics from a session"""
        try:
            queries = self.client.table("scraping_queries") \
                .select("query_topic") \
                .eq("session_id", session_id) \
                .eq("user_id", user_id) \
                .eq("status", "completed") \
                .execute()

            topics = []
            for query in queries.data or []:
                topic = query.get("query_topic")
                if topic and topic not in topics:
                    topics.append(topic)

            return topics
        except Exception as e:
            logger.error(f"Failed to get session topics: {e}")
            return []
