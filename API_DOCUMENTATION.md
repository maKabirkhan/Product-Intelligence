# Product Intelligence API Documentation

## Overview

This document provides complete API documentation for the Product Intelligence System backend.

**Base URL:** `http://localhost:8000`
**API Version:** 3.1.0
**Last Updated:** January 2026

## Authentication

All endpoints (except `/auth/*`) require a JWT token in the Authorization header:

```
Authorization: Bearer <token>
```

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Chat Sessions](#2-chat-sessions)
3. [Scraping Queries](#3-scraping-queries)
4. [RAG Agents](#4-rag-agents)
5. [WebSocket](#5-websocket)
6. [Data Flow](#6-data-flow)

---

## 1. Authentication

Uses Supabase native authentication. Tokens are managed by Supabase.

### POST /auth/signup
Create a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "string",
  "username": "string (optional)"
}
```

**Response (201):**
```json
{
  "message": "User created successfully",
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "username"
  }
}
```

**Response (if email confirmation required):**
```json
{
  "message": "Please check your email to confirm your account",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "username"
  },
  "requires_confirmation": true
}
```

**Errors:**
- `400`: Email already registered
- `400`: Sign up failed

---

### POST /auth/signin
Authenticate and get JWT tokens.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "string"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "username"
  }
}
```

**Errors:**
- `401`: Invalid email or password
- `401`: Authentication failed

---

### POST /auth/refresh
Refresh the access token using a refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:**
- `401`: Invalid refresh token
- `401`: Could not refresh token

---

### POST /auth/signout
Sign out the current user.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "message": "Successfully signed out"
}
```

---

### GET /auth/me
Get current user info.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "username",
  "created_at": "2024-01-01T00:00:00Z",
  "email_confirmed": true
}
```

**Errors:**
- `401`: Invalid or expired token

---

### POST /auth/reset-password
Request a password reset email.

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "message": "If an account exists with this email, a reset link has been sent"
}
```

---

## 2. Chat Sessions

Sessions are like Perplexity AI conversations - they hold multiple queries and can have an associated RAG agent.

### POST /api/sessions
Create a new chat session.

**Headers:** `Authorization: Bearer <token>`

**Request Body (optional):**
```json
{
  "title": "My Research Session"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "user_id": 1,
  "title": null,
  "status": "active",
  "total_queries": 0,
  "total_products_scraped": 0,
  "rag_agent_id": null,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

---

### GET /api/sessions
List all sessions.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `status` (optional): Filter by status (active, completed, archived)
- `limit` (optional): Max results (default: 50, max: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response (200):**
```json
{
  "sessions": [...],
  "total": 10
}
```

---

### GET /api/sessions/{session_id}
Get session details.

**Response (200):**
```json
{
  "id": "uuid",
  "user_id": 1,
  "title": "HDD/Laptop",
  "status": "active",
  "total_queries": 2,
  "total_products_scraped": 45,
  "rag_agent_id": "uuid-or-null",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

---

### PATCH /api/sessions/{session_id}
Update a session.

**Request Body:**
```json
{
  "title": "New Title",
  "status": "completed"
}
```

---

### DELETE /api/sessions/{session_id}
Soft delete a session.

**Note:** Associated RAG agent is NOT deleted.

**Response (200):**
```json
{
  "message": "Session deleted successfully",
  "success": true
}
```

---

### POST /api/sessions/{session_id}/archive
Archive a session.

---

### POST /api/sessions/{session_id}/restore
Restore an archived/deleted session.

---

## 3. Scraping Queries

### POST /api/sessions/{session_id}/queries
Create a new query and start URL collection.

**Important Behavior:**
- If there's a previous query in `urls_collected` status, it's marked as `voided`
- URL collection starts immediately in background
- Session title is auto-updated from query

**Request Body:**
```json
{
  "query_text": "laptop",
  "url_collection_config": {
    "max_pages": 5,
    "limit": 100,
    "collect_all": false
  }
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "user_id": 1,
  "query_text": "laptop",
  "query_topic": "Laptop",
  "collected_urls": [],
  "total_urls_collected": 0,
  "url_collection_config": {...},
  "products_data": [],
  "total_products_scraped": 0,
  "status": "collecting_urls",
  "scraping_progress": {},
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Status Flow:**
```
pending -> collecting_urls -> urls_collected -> scraping -> paused/completed/cancelled/voided/error
```

---

### GET /api/sessions/{session_id}/queries
List all queries in a session.

**Response (200):**
```json
{
  "queries": [...],
  "total": 5
}
```

---

### GET /api/sessions/{session_id}/queries/{query_id}
Get query details including products data.

---

### GET /api/sessions/{session_id}/queries/{query_id}/urls
Get only collected URLs (for displaying before scraping).

**Response (200):**
```json
{
  "query_id": "uuid",
  "query_text": "laptop",
  "status": "urls_collected",
  "collected_urls": [
    {
      "asin": "B07XJ8C8F5",
      "url": "https://amazon.com/dp/B07XJ8C8F5",
      "title": "Product Title",
      "image_url": "https://..."
    }
  ],
  "total_urls_collected": 50,
  "url_collection_config": {...}
}
```

---

### POST /api/sessions/{session_id}/queries/{query_id}/scrape
Start scraping collected URLs.

**Prerequisites:**
- Query must be in `urls_collected` or `paused` status

**Request Body (optional):**
```json
{
  "max_products": 50,
  "skip_ocr": false,
  "skip_ai_analysis": false
}
```

**Response (200):**
```json
{
  "query_id": "uuid",
  "status": "scraping",
  "message": "Scraping started",
  "progress": null
}
```

---

### POST /api/sessions/{session_id}/queries/{query_id}/pause
Pause ongoing scraping.

**Response (200):**
```json
{
  "query_id": "uuid",
  "status": "paused",
  "message": "Scraping paused",
  "progress": {
    "current_index": 15,
    "total": 50,
    "current_asin": "B07...",
    "current_stage": "ocr",
    "products_completed": 14,
    "products_failed": 0
  }
}
```

---

### POST /api/sessions/{session_id}/queries/{query_id}/resume
Resume paused scraping.

---

### POST /api/sessions/{session_id}/queries/{query_id}/cancel
Cancel scraping. Already scraped products are retained.

---

### DELETE /api/sessions/{session_id}/queries/{query_id}
Delete/void a query.

---

### GET /api/sessions/{session_id}/queries/{query_id}/logs
Get scraping logs (for non-WebSocket clients).

**Response (200):**
```json
{
  "query_id": "uuid",
  "logs": [
    {
      "id": "uuid",
      "log_type": "scraping",
      "message": "[5/50] Scraping: Product Title...",
      "progress_current": 5,
      "progress_total": 50,
      "metadata": {"asin": "B07...", "stage": "details"},
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 100
}
```

---

## 4. RAG Agents

### POST /api/agents
Create a RAG agent from session's scraped products.

**Request Body:**
```json
{
  "session_id": "uuid",
  "name": "Custom Agent Name (optional)",
  "description": "Optional description"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "user_id": 1,
  "name": "HDD/Laptop/Soap",
  "description": null,
  "status": "creating",
  "vector_store_id": null,
  "vector_store_provider": "pinecone",
  "total_products": 45,
  "query_topics": ["HDD", "Laptop", "Soap"],
  "source_session_id": "uuid",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "embeddings_created_at": null
}
```

**Agent Status:**
- `creating`: Embeddings being created
- `ready`: Agent ready for chat
- `error`: Creation failed
- `deleted`: Soft deleted

---

### GET /api/agents
List all agents.

**Query Parameters:**
- `status` (optional): Filter by status
- `limit`, `offset`: Pagination

---

### GET /api/agents/{agent_id}
Get agent details.

---

### DELETE /api/agents/{agent_id}
Delete agent (separate from session deletion).

---

### POST /api/agents/{agent_id}/chat
Chat with the RAG agent.

**Request Body:**
```json
{
  "message": "What are the best laptops with 16GB RAM?"
}
```

**Response (200):**
```json
{
  "agent_id": "uuid",
  "message": {
    "role": "assistant",
    "content": "Based on the products in my knowledge base...",
    "metadata": {
      "total_products": 45,
      "topics": ["HDD", "Laptop"]
    }
  },
  "sources": [
    {"asin": "B07...", "title": "Product Title", "relevance": 0.95}
  ]
}
```

**Note:** RAG functionality is a placeholder - full implementation pending.

---

### GET /api/agents/{agent_id}/chat/history
Get chat history.

**Response (200):**
```json
{
  "agent_id": "uuid",
  "messages": [
    {"role": "user", "content": "...", "metadata": null},
    {"role": "assistant", "content": "...", "metadata": {...}}
  ],
  "total": 10
}
```

---

### DELETE /api/agents/{agent_id}/chat/history
Clear chat history.

---

### GET /api/agents/{agent_id}/products
Get products stored in the agent.

**Response (200):**
```json
{
  "agent_id": "uuid",
  "products": [...],
  "total": 45,
  "limit": 50,
  "offset": 0
}
```

---

## 5. WebSocket

### WS /ws/scraping/{query_id}?token={jwt_token}

Real-time scraping progress and logs.

**Connection:**
```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/scraping/${queryId}?token=${jwtToken}`);
```

**Incoming Message Types:**

1. **Connected:**
```json
{
  "type": "connected",
  "query_id": "uuid",
  "status": "scraping",
  "progress": {...},
  "timestamp": "2024-01-01T00:00:00Z"
}
```

2. **History (recent logs):**
```json
{
  "type": "history",
  "logs": [...],
  "timestamp": "2024-01-01T00:00:00Z"
}
```

3. **Log:**
```json
{
  "type": "log",
  "log_type": "scraping|ocr|ai_analysis|success|error|warning|info",
  "message": "[5/50] Scraping: Product Title...",
  "progress_current": 5,
  "progress_total": 50,
  "metadata": {"asin": "B07...", "stage": "details"},
  "timestamp": "2024-01-01T00:00:00Z"
}
```

4. **Progress:**
```json
{
  "type": "progress",
  "progress": {
    "current_index": 5,
    "total": 50,
    "current_asin": "B07...",
    "current_stage": "ocr",
    "products_completed": 4,
    "products_failed": 0
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

5. **Status Change:**
```json
{
  "type": "status_change",
  "old_status": "scraping",
  "new_status": "completed",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

6. **Complete:**
```json
{
  "type": "complete",
  "message": "Scraping completed! 50 products scraped.",
  "total_products": 50,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

7. **Error:**
```json
{
  "type": "error",
  "message": "Scraping failed: Connection timeout",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

8. **Thinking (Perplexity-style):**
Real-time "thinking" updates showing the AI's reasoning process.
```json
{
  "type": "thinking",
  "phase": "url_collection|scraping_product|extracting_data|ocr_processing|ai_analysis|completed|error",
  "title": "Analyzing Search Query",
  "content": "Looking for laptop products matching user query...",
  "details": {
    "asin": "B07...",
    "fields": ["title", "price", "rating"]
  },
  "progress": {
    "current": 5,
    "total": 50,
    "percentage": 10.0
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**Thinking Message Types:**
- `thought`: Internal reasoning step
- `action`: Taking an action (connecting, fetching, etc.)
- `observation`: Result of an action
- `progress`: Progress update with percentage
- `success`: Successful completion
- `warning`: Warning/caution
- `error`: Error occurred
- `summary`: Summary of work done

**Example Thinking Flow:**
```
[thought] Understanding Query: Analyzing search query: "laptop"
[action] Planning Search Strategy: Will search up to 5 pages of results
[action] Connecting to Amazon: Establishing secure browser connection
[action] Navigating to Amazon: Searching for: "laptop"
[observation] Search Results Retrieved: Amazon returned 48 products
[progress] Scanning Search Results: Found 48 products so far (page 1/5)
[success] URL Collection Complete: Successfully collected 48 product URLs
[thought] Planning Scraping Strategy: Will process 48 products
[action] Processing Pipeline: Each product will go through: details → OCR → AI analysis
[progress] Processing Product: Extracting data for: Dell XPS 15... (1/48)
[observation] Data Extracted: Found 12 data fields
[action] Analyzing Product Images: Running OCR on 5 product images
[observation] Image Text Extracted: Extracted 1234 characters (ingredients detected)
[action] Running AI Analysis: Analyzing product data for insights
[observation] Analysis Complete: Identified 2 flags: safety_warning, quality_concern
[success] Product Processed: Successfully completed product 1/48
...
[summary] Scraping Complete: Successfully processed 45 products (93.8% success rate, elapsed: 5.2m)
```

**Outgoing Message Types (Client to Server):**

1. **Ping:**
```json
{"type": "ping"}
```

2. **Get Status:**
```json
{"type": "get_status"}
```

3. **Get Logs:**
```json
{"type": "get_logs", "since": "2024-01-01T00:00:00Z", "limit": 50}
```

---

## 6. Data Flow

### Complete User Flow:

```
1. User signs up/in
   POST /auth/signup or POST /auth/signin
   -> Get JWT token

2. User starts new chat (session created lazily)
   POST /api/sessions/{session_id}/queries
   {query_text: "laptop"}
   -> Session auto-created, URL collection starts

3. Frontend connects to WebSocket for real-time updates
   WS /ws/scraping/{query_id}?token=...
   -> Receive URL collection progress

4. URL collection completes
   GET /api/sessions/{session_id}/queries/{query_id}/urls
   -> Display URLs to user

5. User clicks "Start Scraping"
   POST /api/sessions/{session_id}/queries/{query_id}/scrape
   -> Scraping starts (details, OCR, AI analysis)

6. User can pause/resume/cancel
   POST .../pause | .../resume | .../cancel

7. User can add more queries to same session
   POST /api/sessions/{session_id}/queries
   {query_text: "keyboard"}
   -> Previous unscraped query is voided

8. After all queries complete, user creates RAG agent
   POST /api/agents
   {session_id: "..."}
   -> Agent created with all products from all queries

9. User chats with agent
   POST /api/agents/{agent_id}/chat
   {message: "Which laptop has best battery?"}

10. User can delete session (agent persists)
    DELETE /api/sessions/{session_id}

11. User can delete agent separately
    DELETE /api/agents/{agent_id}
```

### Products Data Structure (Universal Schema):

```json
{
  // Core Identity
  "asin": "B07XJ8C8F5",
  "title": "Product Title",
  "brand": "Brand Name",
  "brand_store_url": "/stores/Brand/page/...",
  "product_url": "https://amazon.com/dp/B07XJ8C8F5",

  // Pricing & Financials
  "current_price": "$99.99",
  "list_price": "$129.99",
  "savings_percent": "-23%",
  "price_per_unit": "$0.50/oz",
  "currency": "USD",
  "coupon": "Apply $5 coupon",

  // Ratings & Social Proof
  "average_rating": "4.5",
  "reviews_count": "1,234",
  "monthly_sales": "10K+ bought in past month",

  // Badges & Designations
  "is_amazons_choice": true,
  "is_climate_pledge": false,
  "is_best_seller": true,
  "badges": ["Amazon's Choice", "Best Seller"],

  // Inventory & Shipping
  "availability": "In Stock",
  "ships_from": "Amazon.com",
  "shipping_cost": "PKR 43,562.40 Shipping & Import Charges",
  "delivery_date": "Wednesday, January 28",

  // Product Details
  "description": "Product description...",
  "bullet_points": ["Feature 1", "Feature 2"],
  "ingredients": "Extracted from specs or OCR",
  "category": "Electronics > Computers > Accessories",

  // Specifications (ALL product-specific details stored here)
  "specifications": {
    "Brand": "Dell",
    "Item Weight": "5 lbs",
    "Dimensions": "15 x 10 x 1 inches",
    "Material": "Plastic",
    "Color": "Black",
    "Scent": "Lavender",
    "Manufacturer": "Dell Inc."
  },

  // Media
  "image_urls": ["url1", "url2", "url3"],
  "image_url": "url1",
  "video_count": 3,

  // OCR Data (text extracted from product images)
  "ocr_text": "Text extracted from all product images...",
  "ocr_status": "SUCCESS",
  "ocr_processed": true,

  // AI Analysis (intelligent insights using GPT)
  "ai_analysis": {
    "summary": "2-3 sentence product summary",
    "key_features": ["Feature 1", "Feature 2"],
    "potential_issues": ["Any concerns"],
    "quality_indicators": ["Positive signals"],
    "flags": ["top_rated", "great_value"],
    "sentiment": "positive",
    "analyzed_at": "2026-01-18T20:34:04Z"
  },

  // Metadata
  "scraped_at": "2026-01-18T20:34:03Z"
}
```

**Field Categories:**
| Category | Fields | Description |
|----------|--------|-------------|
| Core Identity | asin, title, brand, brand_store_url, product_url | Basic product identification |
| Pricing | current_price, list_price, savings_percent, price_per_unit, currency, coupon | All pricing data |
| Ratings | average_rating, reviews_count, monthly_sales | Social proof metrics |
| Badges | is_amazons_choice, is_climate_pledge, is_best_seller, badges | Amazon badges |
| Shipping | availability, ships_from, shipping_cost, delivery_date | Fulfillment info |
| Details | description, bullet_points, ingredients, category | Product content |
| Specifications | specifications | **All product-specific fields** (weight, dimensions, color, etc.) |
| Media | image_urls, image_url, video_count | Visual content |
| OCR | ocr_text, ocr_status, ocr_processed | Image text extraction |
| AI | ai_analysis | GPT-powered insights |
| Metadata | scraped_at | Timestamps |

**Note:** Product-specific fields (scent, weight, dimensions, color, material) are stored in the `specifications` object, making this schema universal for any product type.

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message"
}
```

Common HTTP status codes:
- `400`: Bad request (validation error)
- `401`: Unauthorized (invalid/expired token)
- `404`: Resource not found
- `500`: Server error

---

## Swagger Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
