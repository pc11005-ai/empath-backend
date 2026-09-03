from fastapi import APIRouter

from ..schemas import (
    ChatOut,
    ChatWithMessages,
    CreateChatRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from ..services import chat_service
from ..services.chat_service import to_chat_out

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ChatOut)
def create_chat(payload: CreateChatRequest):
    """Start a brand-new chat with a fresh thread_id and empty context."""
    return chat_service.create_chat(payload.title)


@router.get("", response_model=list[ChatOut])
def list_active_chats():
    """Sidebar list — active (non-trashed) chats, most recently updated first."""
    return chat_service.list_chats(status="active")


@router.get("/{chat_id}", response_model=ChatWithMessages)
def get_chat_detail(chat_id: str):
    """Full message history for a single chat/thread."""
    chat_row = chat_service.get_chat(chat_id)
    return ChatWithMessages(
        chat=to_chat_out(chat_row),
        messages=chat_service.get_messages(chat_id),
    )


@router.post("/{chat_id}/messages", response_model=SendMessageResponse)
def send_message(chat_id: str, payload: SendMessageRequest):
    """
    Send a user message on an existing thread and get EmPath's reply.
    Full prior history for this thread_id is loaded server-side so context
    is remembered across turns.
    """
    user_msg, assistant_msg, chat = chat_service.send_message(chat_id, payload.content)
    return SendMessageResponse(user_message=user_msg, assistant_message=assistant_msg, chat=chat)


@router.delete("/{chat_id}", response_model=ChatOut)
def trash_chat(chat_id: str):
    """Right-click → Delete: soft-delete into Trash (not gone yet)."""
    return chat_service.move_to_trash(chat_id)
