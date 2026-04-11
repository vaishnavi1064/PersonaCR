"""
Embedder — converts CodeChunks into 768-dim vectors using Jina code embeddings
and stores/queries them in a persistent ChromaDB vector database.

Uses fastembed (ONNX-based) instead of sentence-transformers for Python 3.14 compatibility.
"""
from __future__ import annotations

import os
import re
import hashlib
from typing import Any

import chromadb
from chromadb.config import Settings
from fastembed import TextEmbedding

# Singleton model — loaded once, reused across calls
_model: TextEmbedding | None = None
_chroma_client: chromadb.PersistentClient | None = None

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".chroma")
MODEL_NAME = "jinaai/jina-embeddings-v2-base-code"


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        print(f"[Embedder] Loading {MODEL_NAME} via fastembed (first load downloads ONNX model)...")
        _model = TextEmbedding(MODEL_NAME)
        print("[Embedder] Model ready.")
    return _model


def _get_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client


def _collection_name(user_id: str, repo_name: str) -> str:
    """ChromaDB collection names must be 3-63 chars, alphanumeric + hyphens."""
    raw = f"{user_id}__{repo_name}"
    hashed = hashlib.md5(raw.encode()).hexdigest()[:16]
    safe_repo = re.sub(r"[^a-zA-Z0-9-]", "-", repo_name)[:30]
    return f"pcr-{safe_repo}-{hashed}"


def embed_and_store(
    chunks: list,
    user_id: str,
    repo_name: str,
    batch_size: int = 32,
) -> str:
    """
    Embed code chunks and store them in ChromaDB.

    Args:
        chunks: List of CodeChunk objects
        user_id: Supabase user ID (or 'anonymous')
        repo_name: Repository name (used to namespace the collection)
        batch_size: How many chunks to embed at once

    Returns:
        collection_name used in ChromaDB
    """
    model = _get_model()
    client = _get_client()

    col_name = _collection_name(user_id, repo_name)

    # Delete and recreate collection to avoid stale embeddings
    try:
        client.delete_collection(col_name)
    except Exception:
        pass
    collection = client.create_collection(
        name=col_name,
        metadata={"hnsw:space": "cosine"},
    )

    # Embed in batches
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.source for c in batch]

        # fastembed returns a generator — collect to list
        embeddings = list(model.embed(texts))
        # Convert numpy arrays to plain Python lists for ChromaDB
        embeddings_list = [e.tolist() for e in embeddings]

        ids = [
            f"{c.file_path}::{c.function_name}::{c.start_line}"
            for c in batch
        ]
        metadatas = [
            {
                "file_path": c.file_path,
                "language": c.language,
                "function_name": c.function_name,
                "start_line": c.start_line,
                "end_line": c.end_line,
            }
            for c in batch
        ]

        collection.add(
            embeddings=embeddings_list,
            documents=texts,
            ids=ids,
            metadatas=metadatas,
        )

    print(f"[Embedder] Stored {len(chunks)} chunks in collection '{col_name}'")
    return col_name


def query_similar(
    code: str,
    user_id: str,
    repo_name: str,
    n: int = 10,
    language_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    Query ChromaDB for the most similar functions to the given code.

    Args:
        code: Code snippet to find similar functions for
        user_id: Supabase user ID
        repo_name: Repository name
        n: Number of results to return
        language_filter: Optional language to filter by (e.g. 'python')

    Returns:
        List of dicts with keys: source, metadata, distance
    """
    model = _get_model()
    client = _get_client()

    col_name = _collection_name(user_id, repo_name)
    try:
        collection = client.get_collection(col_name)
    except Exception:
        return []

    # fastembed returns a generator
    embedding = list(model.embed([code]))[0].tolist()

    where = {"language": {"$eq": language_filter}} if language_filter else None

    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_embeddings=[embedding],
        n_results=min(n, count),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    if results and results.get("documents"):
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({"source": doc, "metadata": meta, "distance": dist})

    return output


def delete_collection(user_id: str, repo_name: str) -> None:
    """Remove a repo's embeddings from ChromaDB."""
    client = _get_client()
    col_name = _collection_name(user_id, repo_name)
    try:
        client.delete_collection(col_name)
    except Exception:
        pass
