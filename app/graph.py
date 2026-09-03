"""
LangGraph graph that powers EmPath's replies, plus a lightweight intent
classifier that filters out off-topic requests before the expensive main
model is ever called.

Note on state: Supabase is the single source of truth for chat history —
we reload the full conversation from it on every request and pass it in
directly. Because of that, this graph is compiled WITHOUT a persistent
checkpointer. Adding one here would make LangGraph keep its own separate
copy of the conversation per thread_id, on top of the copy we already pass
in each call — silently duplicating the message list a little more each
turn. That both slows every request down (a bigger and bigger context to
send to Gemini) and eventually breaks the call outright. Compiling without
a checkpointer keeps each invocation stateless, fast, and correct.
"""
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
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

OFF_TOPIC_REPLY = (
    "I am EmPath, an emotional support assistant. I can't help with "
    "programming or general knowledge questions."
)

CLASSIFIER_PROMPT = (
    "Is this message related to emotional support or personal feelings? "
    "Respond with exactly one word: YES or NO. No punctuation, no explanation.\n\n"
    "Message: {message}"
)


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _build_llm(model: str, temperature: float = 0.7, max_output_tokens: int | None = None) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    kwargs = {
        "model": model,
        "google_api_key": settings.gemini_api_key,
        "temperature": temperature,
    }
    if max_output_tokens:
        kwargs["max_output_tokens"] = max_output_tokens
    return ChatGoogleGenerativeAI(**kwargs)


def _chat_node(state: ChatState) -> ChatState:
    settings = get_settings()
    # max_output_tokens caps how long a reply can run, which is one of the
    # biggest levers on response time for a chat like this.
    llm = _build_llm(settings.gemini_model, temperature=0.7, max_output_tokens=600)
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
    return graph.compile()  # no checkpointer — see module docstring


_COMPILED_GRAPH = _build_graph()


def is_emotional_support_message(text: str) -> bool:
    """
    Fast, cheap pre-check using a lightweight model: is this message about
    feelings / emotional support at all? Runs before the main model so we
    never spend its quota or time on coding help, trivia, etc.
    """
    settings = get_settings()
    classifier = _build_llm(settings.gemini_classifier_model, temperature=0, max_output_tokens=5)
    result = classifier.invoke(CLASSIFIER_PROMPT.format(message=text))
    answer = (result.content or "").strip().upper()
    return answer.startswith("Y")


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

    result = _COMPILED_GRAPH.invoke({"messages": lc_messages})
    final_message = result["messages"][-1]
    return final_message.content
