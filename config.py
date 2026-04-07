"""
Configuration file for Product Intelligence System
Store all API keys, credentials, and settings here
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# OpenAI Configuration (for AI analysis)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OCR Configuration
OCR_ENGINE = "tesseract"  # Options: "tesseract", "google_vision", "aws_textract"

# For Google Vision OCR (optional)
GOOGLE_CLOUD_CREDENTIALS = os.getenv("GOOGLE_CLOUD_CREDENTIALS")

# For AWS Textract (optional)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Scraper Settings
PLAYWRIGHT_TIMEOUT = 120000
MAX_RETRIES = 3
DELAY_BETWEEN_REQUESTS = 2  # seconds

# Analysis Settings
AI_MODEL = "gpt-4o"  # or "gpt-3.5-turbo" for faster/cheaper
MAX_TOKENS_ANALYSIS = 2000

# Review Scraping Settings
MAX_REVIEWS_PER_PRODUCT = 100

# Amazon Settings
AMAZON_BASE_URL = "https://www.amazon.com"

# User Agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "scraper.log"