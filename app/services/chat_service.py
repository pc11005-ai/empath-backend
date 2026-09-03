"""
All Supabase reads/writes for chats + messages live here, so routers stay thin.
"""
from datetime import datetime, timezone
from fastapi import HTTPException

from ..database import get_supabase
from ..config import get_settings
from ..graph import generate_reply, is_off_topic_request, OFF_TOPIC_REPLY
from ..schemas import ChatOut, MessageOut


def _days_left(deleted_at: str | None, retention_days: int) -> int | None:
    if not deleted_at:
        return None
    deleted = datetime.fromisoformat(deleted_at.replace("Z", "+00:00"))
    elapsed = (datetime.now(timezone.utc) - deleted).days
    return max(retention_days - elapsed, 0)


def to_chat_out(row: dict) -> ChatOut:
    settings = get_settings()
    return ChatOut(
        id=row["id"],
        title=row["title"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row.get("deleted_at"),
        days_left=_days_left(row.get("deleted_at"), settings.trash_retention_days),
    )


def create_chat(title: str | None) -> ChatOut:
    db = get_supabase()
    payload = {"title": title or "New chat"}
    res = db.table("chats").insert(payload).execute()
    return to_chat_out(res.data[0])


def list_chats(status: str) -> list[ChatOut]:
    db = get_supabase()
    res = (
        db.table("chats")
        .select("*")
        .eq("status", status)
        .order("updated_at", desc=True)
        .execute()
    )
    return [to_chat_out(row) for row in res.data]


def get_chat(chat_id: str) -> dict:
    db = get_supabase()
    res = db.table("chats").select("*").eq("id", chat_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Chat not found")
    return res.data[0]


def get_messages(chat_id: str) -> list[MessageOut]:
    db = get_supabase()
    res = (
        db.table("messages")
        .select("*")
        .eq("chat_id", chat_id)
        .order("created_at", desc=False)
        .execute()
    )
    return [MessageOut(**row) for row in res.data]


def send_message(chat_id: str, content: str) -> tuple[MessageOut, MessageOut, ChatOut]:
    db = get_supabase()
    chat_row = get_chat(chat_id)
    if chat_row["status"] != "active":
        raise HTTPException(status_code=400, detail="Cannot message a chat that is in Trash")

    history = [
        {"role": m.role, "content": m.content} for m in get_messages(chat_id)
    ]

    user_row = (
        db.table("messages")
        .insert({"chat_id": chat_id, "role": "user", "content": content})
        .execute()
        .data[0]
    )

     if is_off_topic_request(content):
        reply_text = OFF_TOPIC_REPLY
    else:
        reply_text = generate_reply(thread_id=chat_id, history=history, new_user_message=content)
    
    assistant_row = (
        db.table("messages")
        .insert({"chat_id": chat_id, "role": "assistant", "content": reply_text})
        .execute()
        .data[0]
    )

    update_payload = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if chat_row["title"] == "New chat":
        update_payload["title"] = content[:60] + ("…" if len(content) > 60 else "")
    updated_chat = (
        db.table("chats").update(update_payload).eq("id", chat_id).execute().data[0]
    )

    return MessageOut(**user_row), MessageOut(**assistant_row), to_chat_out(updated_chat)


def move_to_trash(chat_id: str) -> ChatOut:
    db = get_supabase()
    get_chat(chat_id)
    now = datetime.now(timezone.utc).isoformat()
    res = (
        db.table("chats")
        .update({"status": "trash", "deleted_at": now, "updated_at": now})
        .eq("id", chat_id)
        .execute()
    )
    return to_chat_out(res.data[0])


def restore_from_trash(chat_id: str) -> ChatOut:
    db = get_supabase()
    get_chat(chat_id)
    now = datetime.now(timezone.utc).isoformat()
    res = (
        db.table("chats")
        .update({"status": "active", "deleted_at": None, "updated_at": now})
        .eq("id", chat_id)
        .execute()
    )
    return to_chat_out(res.data[0])


def delete_permanently(chat_id: str) -> None:
    db = get_supabase()
    get_chat(chat_id)
    db.table("chats").delete().eq("id", chat_id).execute()
