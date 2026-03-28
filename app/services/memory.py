from __future__ import annotations
from collections import defaultdict, deque
from app.config import get_settings

_store: dict[str, deque] = defaultdict(
    lambda: deque(maxlen=get_settings().max_history_turns * 2))

def get_history(sid: str) -> list[dict]: return list(_store[sid])
def add_turn(sid: str, user: str, asst: str):
    _store[sid].append({"role":"user","content":user})
    _store[sid].append({"role":"assistant","content":asst})
def clear_session(sid: str): _store.pop(sid, None)