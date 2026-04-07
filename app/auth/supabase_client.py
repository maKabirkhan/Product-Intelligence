"""
Supabase Client Configuration
Uses Supabase native authentication system
"""

from supabase import create_client, Client
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # This should be the anon key
SUPABASE_SERVICE_KEY = os.getenv("SECRET_KEY")  # Service role key for admin operations

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL or SUPABASE_KEY is missing from .env file")

# Regular client for user operations (uses anon key)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Admin client for service operations (uses service role key)
supabase_admin: Client = None
if SUPABASE_SERVICE_KEY:
    supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

logger.info(f"Supabase client initialized for: {SUPABASE_URL}")