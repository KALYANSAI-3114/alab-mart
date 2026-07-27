"""
Alab-Mart Conversation Memory
Stores session context and history across conversational turns.
"""

from typing import Dict, Any, List, Optional

class ConversationMemory:
    def __init__(self):
        # Maps session_id -> context dictionary
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Retrieve context for session or create new if not present."""
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "history": [],
                "last_intent": None,
                "last_product": None,
                "last_category": None,
                "last_quantity": 1,
                "cart": []
            }
        return self._sessions[session_id]

    def update_session(self, session_id: str, key_values: Dict[str, Any]) -> None:
        """Update fields inside session memory."""
        session = self.get_session(session_id)
        for key, value in key_values.items():
            if value is not None:
                session[key] = value

    def add_turn(self, session_id: str, role: str, message: str) -> None:
        """Add user or assistant message to session history."""
        session = self.get_session(session_id)
        session["history"].append({"role": role, "message": message})
        # Maintain sliding memory window (last 10 turns)
        if len(session["history"]) > 20:
            session["history"] = session["history"][-20:]

    def clear_session(self, session_id: str) -> None:
        """Clear memory session."""
        if session_id in self._sessions:
            del self._sessions[session_id]

# Global Memory Store Instance
memory_store = ConversationMemory()