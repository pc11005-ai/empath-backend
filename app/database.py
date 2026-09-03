"""
Supabase client. A single shared client instance, created with the
service-role key, is used by the backend only.
"""
from functools import lru_cache
from supabase import create_client, Client

from .config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)
