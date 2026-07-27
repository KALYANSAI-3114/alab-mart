from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_ollama import ChatOllama
from sentence_transformers import CrossEncoder
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables import RunnablePassthrough


THIS_DIR = Path(__file__).resolve().parent
CHROMA_DB_PATH = THIS_DIR / "rag" / "chroma_db"


# Load Embedding Model
embedding = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# Load Existing Chroma Database
vectorstore = Chroma(
    persist_directory=str(CHROMA_DB_PATH),
    embedding_function=embedding
)


# create retriever

retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 10,
        "fetch_k": 20,
        "lambda_mult": 0.5
    }
)


reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank_documents(query, documents, top_k=5):
    pairs = [
        (query, doc.page_content)
        for doc in documents
    ]

    scores = reranker.predict(pairs)

    ranked = sorted(
        zip(scores, documents),
        key=lambda x: x[0],
        reverse=True
    )

    return [
        doc
        for score, doc in ranked[:top_k]
    ]

def format_docs(docs):
    return "\n\n".join(
        [
            f"Document {i+1}\n{doc.page_content}"
            for i, doc in enumerate(docs)
        ]
    )

# connect llm

llm  = ChatOllama(
    model = "qwen2.5:3b",
    temperature = 0
)

# chatprompttemplate


prompt = ChatPromptTemplate.from_template("""
You are ALAB-MART AI Assistant, a professional virtual assistant for ALAB-MART, an AI-focused e-commerce platform.

Your responsibilities:
- Help customers understand products, policies, and services.
- Answer ONLY using the provided context.
- Never make up information.
- If the answer is not present in the context, politely say:
  "I'm sorry, but I couldn't find that information in the ALAB-MART knowledge base."
- Do not mention the context, embeddings, vector database, retrieval process, or AI models.
- Be polite, professional, and concise.
- If multiple products satisfy the user's request, compare them in a clear table.
- If the user asks for recommendations, explain why each recommendation is suitable.
- Preserve technical specifications exactly as provided.
- When answering policy questions (shipping, refund, warranty, returns, payment), provide a concise summary.
- If the question is ambiguous, ask one clarifying question before answering.
- Format the response using Markdown when appropriate.

Context:
{context}

Customer Question:
{question}

Response:
""")

def retrieve_and_rerank(query):
    docs = retriever.invoke(query)
    docs = rerank_documents(query, docs)   # Your reranking function
    return "\n\n".join(doc.page_content for doc in docs)

chain = (
    {
        "context": RunnableLambda(retrieve_and_rerank),
        "question": RunnablePassthrough()
    }
    | prompt
    | llm
    | StrOutputParser()
)


# RAG Response Function

def get_rag_response(question: str) -> str:
    """
    Takes a user's question and returns the RAG answer.
    """
    try:
        response = chain.invoke(question)
        return response
    except Exception as e:
        return f"Error: {str(e)}"
