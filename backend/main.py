import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.database import engine, Base
from backend.routers import auth_router, conversations_router, chat_router, admin_router, speech_router
from backend.ingestion.seed_rbi_kb import seed_database_and_vector_store

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB and seed initial knowledge base + vector store
    print("Starting CHATGPTxIDFC Banking RAG Application...")
    seed_database_and_vector_store()
    yield
    print("Shutting down CHATGPTxIDFC...")

app = FastAPI(
    title="CHATGPTxIDFC — Banking Conversational AI Application",
    description="Production-quality Banking RAG Assistant with strict source-controlled knowledge and anti-hallucination guardrails.",
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS Configuration
origins = ["*"] if settings.ALLOWED_ORIGINS == "*" else [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Timing & Security Middleware
@app.middleware("http")
async def add_process_time_and_security_headers(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    return response

# Global Safe Error Handler to prevent stack trace leakage to clients
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log internal error
    print(f"[Internal Error] Route: {request.url.path}, Error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Something went wrong while processing the request. Please try again."}
    )

# Include API Routers
app.include_router(auth_router.router)
app.include_router(conversations_router.router)
app.include_router(chat_router.router)
app.include_router(admin_router.router)
app.include_router(speech_router.router)

# Serve Frontend Static Assets
frontend_dir = os.path.join(settings.BASE_DIR, "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join(settings.BASE_DIR, "frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "CHATGPTxIDFC Banking RAG API is running. Frontend index.html not yet mounted."}

@app.get("/health")
@app.get("/api/health")
def health_check():
    from backend.database import SessionLocal
    from backend.models import KnowledgeDocument, KnowledgeChunk
    from backend.rag.vector_store import hybrid_vector_store
    from backend.cache.redis_cache import redis_cache
    from sqlalchemy import text

    db_status = "connected"
    db_latency_ms = 0.0
    doc_count = 0
    chunk_count = 0

    t0 = time.time()
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_latency_ms = round((time.time() - t0) * 1000, 2)
        doc_count = db.query(KnowledgeDocument).count()
        chunk_count = db.query(KnowledgeChunk).count()
        hybrid_vector_store.ensure_indexed(db)
        db.close()
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "database": {
            "status": db_status,
            "latency_ms": db_latency_ms,
            "engine": engine.dialect.name,
            "documents_count": doc_count,
            "chunks_count": chunk_count
        },
        "vector_store": {
            "is_indexed": hybrid_vector_store.is_indexed,
            "indexed_records": len(hybrid_vector_store.chunk_records)
        },
        "cache": {
            "status": "active",
            "backend": "redis" if getattr(redis_cache, "is_redis_available", False) else "in_memory_lru"
        },
        "mode": "Zero-Internet Strict Banking Grounded RAG"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
