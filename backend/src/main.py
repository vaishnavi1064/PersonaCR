from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.src.routes.analyze_routes import router as analyze_router

app = FastAPI(title="PersonaCR Backend", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(analyze_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "personacr-backend", "version": "2.0.0"}