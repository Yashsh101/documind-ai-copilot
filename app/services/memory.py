from __future__ import annotations
from collections import defaultdict, deque
from app.config import get_settings

_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=get_settings().max_history_turns * 2))

def get_history(session_id: str) -> list[dict]:
    return list(_store[session_id])

def add_turn(session_id: str, user_msg: str, assistant_msg: str) -> None:
    _store[session_id].append({"role": "user", "content": user_msg})
    _store[session_id].append({"role": "assistant", "content": assistant_msg})

def clear_session(session_id: str) -> None:
    _store.pop(session_id, None)

def list_sessions() -> list[str]:
    return list(_store.keys())