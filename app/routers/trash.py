from fastapi import APIRouter

from ..schemas import ChatOut
from ..services import chat_service
from ..services.cleanup_service import purge_expired_trash

router = APIRouter(prefix="/trash", tags=["trash"])


@router.get("", response_model=list[ChatOut])
def list_trash():
    """
    Trash contents. Expired items (older than the retention window) are
    purged first, so the list returned is always accurate.
    """
    purge_expired_trash()
    return chat_service.list_chats(status="trash")


@router.post("/{chat_id}/restore", response_model=ChatOut)
def restore_chat(chat_id: str):
    """Bring a chat back from Trash (only possible within the retention window)."""
    return chat_service.restore_from_trash(chat_id)


@router.delete("/{chat_id}")
def delete_forever(chat_id: str):
    """Manually, permanently delete a chat (and its messages) right now."""
    chat_service.delete_permanently(chat_id)
    return {"deleted": True, "chat_id": chat_id}
