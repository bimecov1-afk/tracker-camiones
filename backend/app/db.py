from functools import lru_cache

from postgrest import SyncPostgrestClient

from .config import get_settings


@lru_cache
def get_db() -> SyncPostgrestClient:
    s = get_settings()
    key = s.supabase_service_key
    return SyncPostgrestClient(
        s.rest_url,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=15,
    )
