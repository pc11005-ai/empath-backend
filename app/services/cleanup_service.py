"""
Permanently deletes trashed chats whose retention window has expired.
"""
from datetime import datetime, timedelta, timezone

from ..database import get_supabase
from ..config import get_settings


def purge_expired_trash() -> int:
    settings = get_settings()
    db = get_supabase()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.trash_retention_days)

    res = (
        db.table("chats")
        .select("id")
        .eq("status", "trash")
        .lt("deleted_at", cutoff.isoformat())
        .execute()
    )
    expired_ids = [row["id"] for row in res.data]
    if not expired_ids:
        return 0

    db.table("chats").delete().in_("id", expired_ids).execute()
    return len(expired_ids)
