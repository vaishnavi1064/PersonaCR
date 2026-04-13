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

app = FastAPI(
    title="PersonaCR",
    version="2.0.0",
    description=(
        "Personalized multi-agent code review system. "
        "Learns how a developer writes code by analyzing their GitHub repos, "
        "then reviews new code against their personal patterns using 6 AI agents "
        "with CRScore-inspired quality evaluation."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(analyze_router)
app.include_router(review_router)


@app.get("/health", operation_id="health_check")
def health() -> dict:
    """Check if the PersonaCR server is running and responsive."""
    return {"status": "ok", "service": "personacr-backend", "version": "2.0.0"}


# ── MCP Server ────────────────────────────────────────────────────────────────
# Must be created AFTER all routers are registered so all endpoints are visible.
# Mounts at /mcp — any MCP-compatible client (Claude, Cursor, VS Code) can
# connect to http://localhost:8000/mcp to discover and call PersonaCR tools.
from fastapi_mcp import FastApiMCP  # noqa: E402

mcp = FastApiMCP(
    app,
    name="PersonaCR",
    description=(
        "Personalized multi-agent code review system. "
        "Learns how a developer writes code by analyzing their GitHub repos, "
        "then reviews new code against their personal patterns using 6 AI agents "
        "with CRScore-inspired quality evaluation."
    ),
)

mcp.mount()
logger.info("MCP server mounted at /mcp")


# ── Startup warmup ────────────────────────────────────────────────────────────
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
