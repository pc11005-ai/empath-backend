from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class ChatOut(BaseModel):
    id: str  # == thread_id
    title: str
    status: Literal["active", "trash"]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    days_left: int | None = None  # only populated for trashed chats


class MessageOut(BaseModel):
    id: str
    chat_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ChatWithMessages(BaseModel):
    chat: ChatOut
    messages: list[MessageOut]


class CreateChatRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class SendMessageResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
    chat: ChatOut
