"""
LangGraph graph that powers EmPath's replies.
"""
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from .config import get_settings

SYSTEM_PROMPT = """You are EmPath, a warm, patient, emotionally supportive companion.

Your purpose is to help the person feel heard, validated, and a little less
alone with whatever they're going through — stress, sadness, anxiety, a hard
day, or just wanting to think out loud.

How you talk:
- Warm, natural, conversational. Short paragraphs, not bullet-point lectures.
- Validate feelings before offering any suggestions. Reflect back what you
  hear in your own words rather than just repeating it.
- Ask at most one gentle, open-ended question at a time, and only when it
  helps the person keep talking — don't interrogate.
- Never diagnose a mental health condition and never claim to be a
  therapist, doctor, or medical professional. You can gently suggest
  talking to a therapist, counselor, or doctor when that seems genuinely
  useful, without being pushy about it.
- If someone mentions thoughts of suicide, self-harm, or being in danger,
  respond with care, take it seriously, gently encourage them to reach out
  to a crisis line or emergency services right away, and mention that in
  the US they can call or text 988 (the Suicide & Crisis Lifeline), or the
  equivalent local emergency number if they are elsewhere. Stay warm and
  present — don't lecture or lecture-dump a list of resources.
- Keep replies focused and not overly long unless the person is clearly
  looking to process something at length.
"""


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _build_llm() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.7,
    )


def _chat_node(state: ChatState) -> ChatState:
    llm = _build_llm()
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
    response = llm.invoke(messages)
    return {"messages": [response]}


def _build_graph():
    graph = StateGraph(ChatState)
    graph.add_node("chat", _chat_node)
    graph.add_edge(START, "chat")
    graph.add_edge("chat", END)
    return graph.compile(checkpointer=MemorySaver())


_COMPILED_GRAPH = _build_graph()


def generate_reply(thread_id: str, history: list[dict], new_user_message: str) -> str:
    """
    history: list of {"role": "user"|"assistant", "content": str}, oldest first,
             as loaded from Supabase (NOT including new_user_message yet).
    Returns the assistant's reply text.
    """
    lc_messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in history:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        else:
            lc_messages.append(AIMessage(content=msg["content"]))
    lc_messages.append(HumanMessage(content=new_user_message))

    config = {"configurable": {"thread_id": thread_id}}
    result = _COMPILED_GRAPH.invoke({"messages": lc_messages}, config=config)
    final_message = result["messages"][-1]
    return final_message.content
