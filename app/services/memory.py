"""
DocuMind v3 — Memory System

Implements both short-term (conversation window) and long-term (persistent) memory.
Memory is injected into prompts for context-aware responses.
"""
import json
import os
import time
from typing import List, Dict, Optional
from collections import defaultdict
from app.config import get_settings, logger

s = get_settings()

# In-memory session store (production: use Redis)
_session_memory: Dict[str, List[Dict]] = defaultdict(list)


class MemoryManager:
    """
    Manages conversation memory for a session.
    
    Short-term: Last N turns kept in memory window (configurable)
    Long-term: Full conversation persisted to disk for recall
    """

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.window_size = s.memory_window_size

    @property
    def turns(self) -> List[Dict]:
        return _session_memory[self.session_id]

    def add_turn(self, user_msg: str, assistant_msg: str) -> None:
        """Record a conversation turn."""
        turn = {
            "user": user_msg,
            "assistant": assistant_msg,
            "timestamp": time.time(),
        }
        _session_memory[self.session_id].append(turn)

        # Trim to prevent unbounded growth
        if len(_session_memory[self.session_id]) > self.window_size * 2:
            self._persist_to_disk()
            _session_memory[self.session_id] = _session_memory[self.session_id][-self.window_size:]

    def get_short_term(self) -> List[Dict]:
        """Get the most recent turns within the memory window."""
        return self.turns[-self.window_size:]

    def get_context_string(self) -> str:
        """
        Format recent memory as a string for prompt injection.
        Returns empty string if no history exists.
        """
        recent = self.get_short_term()
        if not recent:
            return ""

        lines = []
        for turn in recent:
            lines.append(f"User: {turn['user']}")
            # Truncate long assistant responses in memory context
            assistant_text = turn['assistant']
            if len(assistant_text) > 300:
                assistant_text = assistant_text[:300] + "..."
            lines.append(f"Assistant: {assistant_text}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all memory for this session."""
        _session_memory[self.session_id] = []
        logger.info(f"Memory cleared for session {self.session_id}")

    def _persist_to_disk(self) -> None:
        """Persist conversation history to disk for long-term recall."""
        try:
            memory_dir = os.path.join(s.data_dir, "memory")
            os.makedirs(memory_dir, exist_ok=True)
            filepath = os.path.join(memory_dir, f"{self.session_id}.json")

            existing = []
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)

            existing.extend(self.turns)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(existing[-100], f)  # Keep last 100 turns on disk

            logger.info(f"Persisted {len(self.turns)} turns to disk for session {self.session_id}")
        except Exception as e:
            logger.error(f"Memory persistence failed: {e}")

    def load_long_term(self) -> List[Dict]:
        """Load long-term memory from disk."""
        try:
            filepath = os.path.join(s.data_dir, "memory", f"{self.session_id}.json")
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load long-term memory: {e}")
        return []

    @property
    def stats(self) -> dict:
        return {
            "session_id": self.session_id,
            "short_term_turns": len(self.turns),
            "window_size": self.window_size,
        }
