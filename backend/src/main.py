import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.src.routes.analyze_routes import router as analyze_router
from backend.src.routes.review_routes import router as review_router

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(title="PersonaCR Backend", version="2.0.0")


@app.on_event("startup")
async def warmup_models() -> None:
    """Preload ML models on server start so the first request isn't slow."""
    try:
        from backend.src.evaluation.sts_scorer import _get_sts_model
        _get_sts_model()
        logger.info("MiniLM STS model preloaded")
        print("MiniLM STS model preloaded")
    except Exception as e:
        logger.warning("Model warmup failed (non-fatal): %s", e)
        print(f"Model warmup failed (non-fatal): {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(analyze_router)
app.include_router(review_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "personacr-backend", "version": "2.0.0"}