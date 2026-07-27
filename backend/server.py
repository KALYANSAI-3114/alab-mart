"""
Alab-Mart FastAPI Backend Server
Tailored for structure:
  - Root: /frontend, /voices, /voice_assistant, /ai
  - Backend: /backend (server.py, database.py, products.py, assistant/)
"""

import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, List, Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

# Imports from backend files
from .database import (
    init_db,
    get_connection,
    create_user,
    find_user_by_email,
    find_public_user,
    create_order,
    list_orders,
    hash_password,
)
from .products import PRODUCTS
from .assistant.agent import shopping_agent
from ai.rag.rag import get_rag_response # Import the RAG response function

# Lifespan event handler (modern FastAPI startup)
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Alab-Mart API", version="1.0.0", lifespan=lifespan)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve project paths dynamically relative to backend/server.py
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
IMAGES_DIR = PROJECT_ROOT / "images"

# Check if required folders exist
if not FRONTEND_DIR.exists():
    print(f"Warning: Frontend directory not found at {FRONTEND_DIR}")
if not IMAGES_DIR.exists():
    print(f"Warning: Images directory not found at {IMAGES_DIR}")

# Serve product images (they live at project root, outside /frontend)
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


# ==========================================
# PYDANTIC SCHEMAS
# ==========================================

class UserRegisterSchema(BaseModel):
    email: EmailStr
    password: str

class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str

class CheckoutSchema(BaseModel):
    user_id: int
    items: List[Any]
    total: int
    payment_method: str = "Credit Card"

class CommandSchema(BaseModel):
    command: str
    session_id: Optional[str] = "default_session"

class SpeakSchema(BaseModel):
    text: str

class ChatSchema(BaseModel):
    query: str


def remove_temp_file(path: str):
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Error removing temp file {path}: {e}")


# ==========================================
# E-COMMERCE & AUTH API ROUTES
# ==========================================

@app.get("/api/products")
async def get_products():
    return PRODUCTS

@app.post("/api/register")
async def register(payload: UserRegisterSchema):
    existing_user = find_user_by_email(payload.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    user = create_user(payload.email, hash_password(payload.password))
    return {"success": True, "user": user}

@app.post("/api/login")
async def login(payload: UserLoginSchema):
    user = find_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user["password_hash"] != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    return {
        "success": True, 
        "user": {"id": user["id"], "email": user["email"], "created_at": user["created_at"]}
    }

@app.post("/api/checkout")
async def checkout(payload: CheckoutSchema):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    order = create_order(
        user_id=payload.user_id,
        items=payload.items,
        total=payload.total,
        payment_method=payload.payment_method
    )
    return {"success": True, "order": order}

@app.get("/api/orders/{user_id}")
async def get_user_orders(user_id: int):
    orders = list_orders(user_id)
    return {"success": True, "orders": orders}


# ==========================================
# VOICE & AI ASSISTANT ENDPOINTS
# ==========================================

@app.post("/assistant/voice")
async def assistant_voice(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    session_id: str = Form("default_session")
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        contents = await audio.read()
        temp_audio.write(contents)
        temp_path = temp_audio.name

    background_tasks.add_task(remove_temp_file, temp_path)

    result = shopping_agent.process_voice_input(temp_path, session_id)

    action = result.get("action_executed") or {}
    action_type = action.get("type")

    return {
        "reply": result.get("assistant_reply", ""),
        "user_text": result.get("user_text", ""),
        "cart": result.get("cart", []),
        "checkout": action_type == "CHECKOUT",
        "listen_again": False,
        "session_id": result.get("session_id"),
        "action": action_type,
        "context": result.get("context", {})
    }
@app.post("/assistant/command")
async def assistant_command(payload: CommandSchema):

    result = shopping_agent.process_text_command(
        payload.command,
        payload.session_id
    )

    action = result.get("action_executed") or {}
    action_type = action.get("type")

    return {
        "reply": result.get("assistant_reply", ""),
        "user_text": result.get("user_text", ""),
        "cart": result.get("cart", []),
        "checkout": action_type == "CHECKOUT",
        "listen_again": not result.get("should_close", False),
        "session_id": result.get("session_id"),
        "action": action_type,
        "context": result.get("context", {})
    }
@app.post("/assistant/speak")
async def assistant_speak(payload: SpeakSchema, background_tasks: BackgroundTasks):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_speech:
        speech_path = temp_speech.name

    try:
        from gtts import gTTS
        tts = gTTS(text=payload.text, lang="en")
        tts.save(speech_path)
        
        background_tasks.add_task(remove_temp_file, speech_path)
        return FileResponse(speech_path, media_type="audio/mpeg", filename="speech.mp3")
    except Exception as e:
        remove_temp_file(speech_path)
        raise HTTPException(status_code=500, detail="TTS synthesis failed")


# ==========================================
# RAG ASSISTANT ENDPOINT (llm.html chat UI)
# ==========================================

@app.post("/api/chat")
def rag_chat(payload: ChatSchema):
    """
    Sync endpoint (not async def) so FastAPI runs the blocking RAG pipeline
    (Chroma retrieval + reranking + Ollama call) in a worker thread instead
    of blocking the event loop.
    """
    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    answer = get_rag_response(payload.query.strip())
    return {"response": answer}


# ==========================================
# FRONTEND HTML & STATIC FILE SERVING
# ==========================================

@app.get("/llm.html")
async def rag_assistant():
    llm_path = FRONTEND_DIR / "llm.html"
    if llm_path.exists():
        return FileResponse(llm_path)
    raise HTTPException(status_code=404, detail="LLM page not found")

# Serve all static assets (css, js, images) from frontend/
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    print("Starting Alab-Mart FastAPI server on http://localhost:8000")
    uvicorn.run(
        "backend.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )