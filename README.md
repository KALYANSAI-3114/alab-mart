# alab-mart

alab-mart is an AI-focused e-commerce platform built to demonstrate two practical AI applications inside one product experience:

- RAG product assistant: a retrieval-augmented chat experience for questions about products, store policies, and recommendations.
- Voice shopping assistant: a live cart assistant that accepts spoken commands and updates the shopping cart in real time.

The project combines a FastAPI backend, a browser storefront, a local RAG pipeline, and a voice workflow powered by Whisper.cpp and gTTS.

## What is included

- Storefront UI for browsing products, authentication, cart management, and checkout.
- `llm.html` for the RAG assistant chat experience.
- Bottom-right Alab widget for voice or text shopping commands.
- Local SQLite persistence for users and orders.
- Product search and demo content designed to showcase AI-assisted shopping.

## Project structure

- `backend/` - FastAPI server, database access, product catalog, and assistant logic.
- `frontend/` - Store pages, styles, and browser-side assistant UI.
- `ai/rag/` - RAG implementation, embeddings, vector store, and notebook used to rebuild the knowledge base.
- `whisper.cpp/` - local Whisper.cpp checkout and build output used for speech-to-text.
- `images/` - product and category assets served by the backend.

## Prerequisites

- Python 3.10+.
- `pip` for Python package installation.
- Ollama for the RAG assistant.
- Whisper.cpp if you want the voice assistant to transcribe audio locally.

## Setup

### 1. Install the core backend dependencies

From the project root:

```bash
cd backend
pip install -r requirements.txt --break-system-packages
```

### 2. Install the RAG dependencies

```bash
cd ..
pip install -r ai/rag/requirements.txt --break-system-packages
```

### 3. Start Ollama for the RAG assistant

The RAG pipeline uses `qwen2.5:3b` by default:

```bash
ollama pull qwen2.5:3b
ollama serve
```

### 4. Download and store Whisper.cpp in the project

Place the Whisper.cpp source tree at the project root so the assistant can find it consistently:

```bash
git clone https://github.com/ggerganov/whisper.cpp.git whisper.cpp
```

Recommended local layout after setup:

```text
alab-mart\whisper.cpp\
alab-mart\whisper.cpp\build\bin\Release\whisper-cli.exe
alab-mart\whisper.cpp\models\ggml-base.en.bin
```

Download a Whisper model from the Whisper.cpp releases or model download scripts, then store it inside `whisper.cpp/models/` or another local path of your choice. If you keep the binary or model somewhere else, point the backend to it with environment variables before starting the server:

```bash
set WHISPER_BIN=d:\path\to\whisper-cli.exe
set WHISPER_MODEL=d:\path\to\ggml-base.en.bin
```

On macOS or Linux, use the equivalent `export` commands.

## Run the application

```bash
cd backend
python server.py
```

Open the store at:

```text
http://localhost:8000
```

The RAG assistant is available at:

```text
http://localhost:8000/llm.html
```

## AI features

### RAG assistant

The assistant on `llm.html` answers questions using the Chroma-backed retrieval pipeline in `ai/rag/rag.py`. It is designed to respond only from the indexed knowledge base and to fail gracefully if the RAG stack is not available.

### Voice shopping assistant

The Alab widget in the storefront supports typed or spoken shopping commands such as adding items, removing items, updating quantity, and checking out. When Whisper.cpp is configured correctly, speech is transcribed locally before the assistant applies the cart action.

## Notes

- `backend/assistant/` is the active shopping assistant used by the server.
- `ai/voice_assistant/` contains an earlier experimental assistant implementation kept for reference.
- The generated SQLite database and local model files are intended to stay on your machine, not in version control.

## Demo flow

1. Start the backend.
2. Open the storefront and add a few products to the cart using voice prompt.
3. Open `llm.html` to ask product or policy questions.
4. Use the Alab widget to test typed or spoken shopping commands.

