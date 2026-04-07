# Product Intelligence System - Backend

> Amazon Product Scraper & RAG Chatbot API built with FastAPI, Playwright, and Supabase

## Quick Start

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Start the server
python main.py

# 3. Open API documentation
open http://localhost:8000/docs
```

## Features

- **Supabase Native Authentication** - Secure user auth with JWT tokens
- **Session-Based Architecture** - Perplexity AI-style chat sessions
- **Amazon Product Scraping** - Collect URLs and scrape product details
- **Real-time WebSocket Updates** - Live "thinking" logs during scraping
- **OCR Processing** - Extract text from product images (Tesseract)
- **AI Analysis** - Analyze products with OpenAI
- **RAG Agents** - Create chatbots from scraped products (architecture ready)
- **Scraping Control** - Pause, resume, cancel operations

## API Endpoints

### Authentication (`/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup` | Register new user |
| POST | `/auth/signin` | Login and get tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/signout` | Sign out user |
| GET | `/auth/me` | Get current user info |
| POST | `/auth/reset-password` | Request password reset |

### Sessions (`/api/sessions`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions` | Create new session |
| GET | `/api/sessions` | List all sessions |
| GET | `/api/sessions/{id}` | Get session details |
| PATCH | `/api/sessions/{id}` | Update session |
| DELETE | `/api/sessions/{id}` | Delete session |

### Scraping Queries (`/api/sessions/{session_id}/queries`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `.../queries` | Create query & start URL collection |
| GET | `.../queries/{id}/urls` | Get collected URLs |
| POST | `.../queries/{id}/scrape` | Start scraping |
| POST | `.../queries/{id}/pause` | Pause scraping |
| POST | `.../queries/{id}/resume` | Resume scraping |
| POST | `.../queries/{id}/cancel` | Cancel scraping |

### RAG Agents (`/api/agents`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/agents` | Create agent from session |
| GET | `/api/agents` | List all agents |
| POST | `/api/agents/{id}/chat` | Chat with agent |
| GET | `/api/agents/{id}/chat/history` | Get chat history |

### WebSocket (`/ws`)
| Protocol | Endpoint | Description |
|----------|----------|-------------|
| WS | `/ws/scraping/{query_id}?token=...` | Real-time scraping logs |

## Technology Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI |
| Database | Supabase (PostgreSQL) |
| Authentication | Supabase Native Auth |
| Web Scraping | Playwright (Chromium) |
| OCR | Tesseract (pytesseract) |
| AI Analysis | OpenAI GPT |
| Real-time | WebSocket |

## Project Structure

```
Product-intelligence-system-Backend/
├── main.py                      # Application entry point
├── app/
│   ├── auth/
│   │   ├── supabase_client.py  # Supabase client
│   │   └── utils.py            # Auth utilities
│   ├── routers/
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── sessions.py         # Session management
│   │   ├── queries.py          # Scraping queries
│   │   ├── agents.py           # RAG agents
│   │   └── websocket.py        # Real-time updates
│   ├── schemas/
│   │   └── sessions.py         # Pydantic models
│   ├── db/
│   │   └── session_manager.py  # Database operations
│   └── services/
│       └── thinking_logger.py  # Perplexity-style logs
├── scrapers/
│   ├── amazon_scraper.py       # URL collection
│   ├── amazon_product_scraper.py # Product details
│   ├── ocr_processor.py        # Image OCR
│   └── ai_analyzer.py          # AI analysis
├── requirements.txt
├── .env                        # Environment variables
├── database_migration.sql      # Database schema
└── API_DOCUMENTATION.md        # Complete API docs
```

## Environment Variables

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SECRET_KEY=your-service-role-key

# OpenAI
OPENAI_API_KEY=your-openai-key

# Server
HOST=0.0.0.0
PORT=8000
```

## Installation

```bash
# Clone repository
git clone <repo-url>
cd Product-intelligence-system-Backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials

# Run database migration in Supabase SQL editor
# (copy contents of database_migration.sql)

# Start server
python main.py
```

## User Flow

```
1. Sign up/Sign in → Get JWT tokens
2. Create session (or auto-created with first query)
3. Submit query → URL collection starts
4. Connect WebSocket → Receive real-time "thinking" logs
5. View collected URLs
6. Start scraping → Products scraped with OCR & AI
7. Pause/Resume/Cancel as needed
8. Create RAG agent from session
9. Chat with agent about products
```

## Documentation

- **API_DOCUMENTATION.md** - Complete API reference with examples
- **Swagger UI** - Interactive docs at `/docs`
- **ReDoc** - Alternative docs at `/redoc`

## Testing with Postman

See `API_DOCUMENTATION.md` for complete Postman collection setup.

Quick test:
```bash
# Sign up
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# Health check
curl http://localhost:8000/
```

---

**Version:** 3.0.0
**Python:** 3.11+
**Status:** Production Ready
