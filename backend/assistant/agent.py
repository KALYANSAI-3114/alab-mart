"""
Alab-Mart AI Agent Controller
Integrates Whisper transcription, Intent parsing, Session Context, and Execution.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from unittest import result
from .memory import memory_store
from .intent import IntentParser
from .executor import StoreExecutor
from ..products import PRODUCTS

class ShoppingAgent:
    def __init__(self):
        self.intent_parser = IntentParser()
        self.executor = StoreExecutor(PRODUCTS)

    def process_voice_input(self, audio_path: str, session_id: str) -> Dict[str, Any]:
        """
        Process recorded audio via Whisper.cpp and execute shopping command.
        """
        # 1. Transcribe audio using local Whisper.cpp binary
        user_text = self._transcribe_audio(audio_path)
        if not user_text:
            return {
                "user_text": "",
                "assistant_reply": "I'm sorry, I couldn't hear that clearly. Could you repeat?",
                "session_id": session_id,
                "should_close": False
            }

        # 2. Process text command
        return self.process_text_command(user_text, session_id)

    def process_text_command(self, user_text: str, session_id: str) -> Dict[str, Any]:
        """
        Process natural text command using session memory context.
        """
        session_data = memory_store.get_session(session_id)

        print(f"\nSESSION ID: {session_id}")
        # Parse intent using current text and context memory
        parsed_intent = self.intent_parser.parse(user_text, session_data, PRODUCTS)

        # Execute store logic
        reply, updated_session, action = self.executor.execute(parsed_intent, session_data)

        # Update memory store
        memory_store.update_session(session_id, updated_session)
        memory_store.add_turn(session_id, "user", user_text)
        memory_store.add_turn(session_id, "assistant", reply)

        return {
            "user_text": user_text,
            "assistant_reply": reply,
            "action_executed": action,
            "cart": updated_session.get("cart", []),
            "should_close": parsed_intent.get("should_close", False),
            "context": {
                "last_product": updated_session.get("last_product"),
                "last_category": updated_session.get("last_category")
            },
            "session_id": session_id
        }

    def _transcribe_audio(self, audio_path: str) -> str:
        """
        Execute local whisper.cpp executable for speech-to-text.

        Configure via env vars if your whisper.cpp build lives elsewhere:
          WHISPER_BIN   - path to the whisper.cpp CLI binary
          WHISPER_MODEL - path to the ggml model file
        Defaults match the project layout described in README.md
        (a `whisper.cpp/` folder at the project root).
        """
        project_root = Path(__file__).resolve().parents[2]

        default_bin_candidates = [
            project_root / "whisper.cpp" / "build" / "bin" / "Release" / "whisper-cli.exe",
            project_root / "whisper.cpp" / "build" / "bin" / "whisper-cli",
            project_root / "whisper.cpp" / "build" / "bin" / "main",
            project_root / "whisper.cpp" / "main",
        ]
        whisper_bin = os.getenv("WHISPER_BIN")
        if not whisper_bin:
            whisper_bin = next((str(p) for p in default_bin_candidates if p.exists()), str(default_bin_candidates[0]))

        whisper_model = os.getenv(
            "WHISPER_MODEL",
            str(project_root / "whisper.cpp" / "ggml-base.en.bin"),
        )

        if not os.path.exists(whisper_bin):
            print(f"[voice] Whisper binary not found at {whisper_bin}. "
                  f"Set WHISPER_BIN / WHISPER_MODEL env vars to point at your whisper.cpp build.")
            return ""
        if not os.path.exists(whisper_model):
            print(f"[voice] Whisper model not found at {whisper_model}.")
            return ""
        if not os.path.exists(audio_path):
            return ""

        try:
            cmd = [whisper_bin, "-m", whisper_model, "-f", audio_path, "-nt"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
            print("\n========== RAW WHISPER OUTPUT ==========")
            print(result.stdout)
            print("=======================================\n")

            return result.stdout.strip()
        except Exception as e:
            print(f"Whisper transcription error: {e}")
            return ""

# Global Agent Instance
shopping_agent = ShoppingAgent()