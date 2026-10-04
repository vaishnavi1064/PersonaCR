"""
Embedder — converts CodeChunks into 768-dim vectors using Jina code embeddings
and stores/queries them in a persistent ChromaDB vector database.

Uses fastembed (ONNX-based) instead of sentence-transformers for Python 3.14 compatibility.
"""
from __future__ import annotations

import logging
import os
import re
import hashlib
from typing import Any
from urllib.parse import urlparse

import chromadb
from chromadb.config import Settings
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

# Singleton model — loaded once, reused across calls
_model: TextEmbedding | None = None
# chromadb stubs treat PersistentClient as a function, not a type.
_chroma_client: Any | None = None

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".chroma")
MODEL_NAME = "jinaai/jina-embeddings-v2-base-code"
# Jina v2 supports long context; cap inputs to avoid OOM / ONNX edge cases on large files.
MAX_EMBED_CHARS = 60_000
# Memory is driven by sequence length, not chunk count: attention is O(tokens²) per
# text and fastembed pads every text in a batch to the longest one. Measured in the
# backend image: 32 function-sized texts ≈ +0.5 GiB, one ~3k-token file ≈ +1.6 GiB,
# one ~7.5k-token file → SIGKILL. So each text is capped at MAX_EMBED_TOKENS and each
# batch keeps (len(batch) × longest tokens) ≤ EMBED_TOKEN_BUDGET, which bounds a
# batch's cost by that of a single EMBED_TOKEN_BUDGET-token text.
MAX_EMBED_TOKENS = int(os.getenv("MAX_EMBED_TOKENS", "2048"))
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "32"))
EMBED_TOKEN_BUDGET = int(os.getenv("EMBED_TOKEN_BUDGET", str(MAX_EMBED_TOKENS)))
# Fallback token estimate when the fastembed tokenizer is not reachable (code ≈ 3–4 chars/token).
_CHARS_PER_TOKEN_EST = 3
# Chroma requires unique string ids; keep under typical 512-byte limits for deep paths.
MAX_ID_LEN = 480


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        logger.info("Loading %s via fastembed (first load may download ONNX)...", MODEL_NAME)
        _model = TextEmbedding(MODEL_NAME)
        tokenizer = _get_tokenizer(_model)
        if tokenizer is not None:
            # Applies to every embed call (indexing and queries).
            tokenizer.enable_truncation(max_length=MAX_EMBED_TOKENS)
        else:
            logger.warning("fastembed tokenizer not reachable; falling back to char-based caps")
        logger.info("Embedding model ready (max %s tokens/text).", MAX_EMBED_TOKENS)
    return _model


def _get_tokenizer(model: Any) -> Any | None:
    """fastembed keeps its HF `tokenizers.Tokenizer` at model.model.tokenizer (not public API)."""
    tokenizer = getattr(getattr(model, "model", None), "tokenizer", None)
    if tokenizer is None or not hasattr(tokenizer, "enable_truncation"):
        return None
    return tokenizer


def _token_counts(model: Any, texts: list[str]) -> list[int]:
    """
    Post-truncation token count per text (what the ONNX model will actually see).

    fastembed enables padding-to-longest on its tokenizer, so encode_batch pads every
    text to the longest one in the call and len(ids) would report that for all texts.
    Count real tokens via the attention mask instead (padding stays enabled — fastembed
    needs it to batch).
    """
    tokenizer = _get_tokenizer(model)
    if tokenizer is None:
        return [min(MAX_EMBED_TOKENS, len(t) // _CHARS_PER_TOKEN_EST + 1) for t in texts]
    return [sum(enc.attention_mask) for enc in tokenizer.encode_batch(texts)]


def _token_budget_batches(
    token_counts: list[int],
    max_items: int,
    token_budget: int,
) -> list[list[int]]:
    """
    Group indices (in order) so each batch has ≤ max_items texts and
    len(batch) × max(tokens in batch) ≤ token_budget. A text over budget on its
    own still gets a batch of one (it is already capped at MAX_EMBED_TOKENS).
    """
    batches: list[list[int]] = []
    current: list[int] = []
    longest = 0
    for idx, n in enumerate(token_counts):
        new_longest = max(longest, n)
        if current and (len(current) >= max_items or (len(current) + 1) * new_longest > token_budget):
            batches.append(current)
            current, new_longest = [], n
        current.append(idx)
        longest = new_longest
    if current:
        batches.append(current)
    return batches


def _get_client() -> Any:
    """
    CHROMADB_URL set (e.g. k8s ``http://chromadb:8000``) → HttpClient to that server.
    Unset → embedded PersistentClient under backend/.chroma (local dev default).
    """
    global _chroma_client
    if _chroma_client is None:
        settings = Settings(anonymized_telemetry=False)
        chroma_url = os.getenv("CHROMADB_URL", "").strip()
        if chroma_url:
            parsed = urlparse(chroma_url)
            if not parsed.hostname:
                raise ValueError(f"CHROMADB_URL has no host: {chroma_url!r}")
            ssl = parsed.scheme == "https"
            port = parsed.port or (443 if ssl else 8000)
            logger.info("Using ChromaDB HttpClient at %s:%s", parsed.hostname, port)
            _chroma_client = chromadb.HttpClient(
                host=parsed.hostname,
                port=port,
                ssl=ssl,
                settings=settings,
            )
        else:
            os.makedirs(CHROMA_DIR, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(
                path=CHROMA_DIR,
                settings=settings,
            )
    return _chroma_client


def _collection_name(user_id: str, repo_name: str) -> str:
    """ChromaDB collection names must be 3-63 chars, alphanumeric + hyphens."""
    raw = f"{user_id}__{repo_name}"
    hashed = hashlib.md5(raw.encode()).hexdigest()[:16]
    safe_repo = re.sub(r"[^a-zA-Z0-9-]", "-", repo_name)[:30]
    return f"pcr-{safe_repo}-{hashed}"


def _truncate_text(text: str) -> str:
    limit = MAX_EMBED_CHARS
    if _model is not None and _get_tokenizer(_model) is None:
        limit = min(limit, MAX_EMBED_TOKENS * _CHARS_PER_TOKEN_EST)
    if len(text) <= limit:
        return text
    return text[:limit]


def _vec_to_list(vec: Any) -> list[float]:
    if hasattr(vec, "tolist"):
        return vec.tolist()
    return list(vec)


def _chunk_id(chunk: Any) -> str:
    raw = f"{chunk.file_path}::{chunk.function_name}::{chunk.start_line}"
    if len(raw) <= MAX_ID_LEN:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:24]
    head = raw[: MAX_ID_LEN - len(digest) - 2]
    return f"{head}__{digest}"


def _chunk_metadata(chunk: Any) -> dict[str, str | int | float | bool]:
    """Chroma metadata values must be str, int, float, or bool (no nested dicts)."""
    return {
        "file_path": str(chunk.file_path),
        "language": str(chunk.language),
        "function_name": str(chunk.function_name),
        "start_line": int(chunk.start_line),
        "end_line": int(chunk.end_line),
        "granularity": str(getattr(chunk, "granularity", "function")),
    }


def embed_and_store(
    chunks: list,
    user_id: str,
    repo_name: str,
    batch_size: int | None = None,
) -> dict[str, Any]:
    """
    Embed code chunks and store them in ChromaDB.

    Args:
        chunks: List of CodeChunk objects
        user_id: Supabase user ID (or 'anonymous')
        repo_name: Repository name (used to namespace the collection)
        batch_size: Max chunks per batch (default EMBED_BATCH_SIZE); batches are also
            split so len(batch) × longest tokens ≤ EMBED_TOKEN_BUDGET

    Returns:
        dict with keys: collection (name), chunks_embedded (int), batches (int)
    """
    if not chunks:
        return {"collection": "", "chunks_embedded": 0}

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
        metadata={"hnsw:space": "cosine", "user_id": user_id},
    )

    # Embed + upsert one bounded batch at a time; vectors are never accumulated
    # across batches.
    texts_all = [_truncate_text(c.source) for c in chunks]
    batches = _token_budget_batches(
        _token_counts(model, texts_all),
        max_items=batch_size or EMBED_BATCH_SIZE,
        token_budget=EMBED_TOKEN_BUDGET,
    )
    for idxs in batches:
        batch = [chunks[i] for i in idxs]
        texts_in = [texts_all[i] for i in idxs]
        documents = texts_in  # store same text as embedded (consistent retrieval)

        # fastembed returns a generator — collect to list; batch_size matches ours so
        # fastembed does not re-group texts.
        embeddings = list(model.embed(texts_in, batch_size=len(texts_in)))
        if len(embeddings) != len(batch):
            raise RuntimeError(
                f"Embedding count mismatch: got {len(embeddings)}, expected {len(batch)}"
            )
        embeddings_list = [_vec_to_list(e) for e in embeddings]

        ids = [_chunk_id(c) for c in batch]
        metadatas = [_chunk_metadata(c) for c in batch]

        collection.add(
            embeddings=embeddings_list,
            documents=documents,
            ids=ids,
            metadatas=metadatas,
        )

    logger.info(
        "Stored %s chunks in Chroma collection %s (%s batches)",
        len(chunks), col_name, len(batches),
    )
    return {"collection": col_name, "chunks_embedded": len(chunks), "batches": len(batches)}


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
    code_in = _truncate_text(code)
    embedding = _vec_to_list(list(model.embed([code_in]))[0])

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


def query_similar_staged(
    code: str,
    user_id: str,
    repo_name: str,
    n_files: int = 3,
    n_functions: int = 10,
    language_filter: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Two-stage retrieval following Ringer (2025):
      Stage 1 — embed the query and find the most similar *files* using
                 file-level summary chunks (granularity='file').
      Stage 2 — within those files, find the most similar *functions*
                 (granularity='function').

    Args:
        code: Code snippet to find similar patterns for
        user_id: Supabase user ID
        repo_name: Repository name
        n_files: Number of top files to surface in Stage 1
        n_functions: Number of functions to return from Stage 2
        language_filter: Optional language to filter both stages

    Returns:
        dict with 'files' (stage-1 results) and 'functions' (stage-2 results),
        each a list of dicts with keys: source, metadata, distance
    """
    model = _get_model()
    client = _get_client()

    col_name = _collection_name(user_id, repo_name)
    try:
        collection = client.get_collection(col_name)
    except Exception:
        return {"files": [], "functions": []}

    count = collection.count()
    if count == 0:
        return {"files": [], "functions": []}

    code_in = _truncate_text(code)
    embedding = _vec_to_list(list(model.embed([code_in]))[0])

    # ── Stage 1: file-level chunks ────────────────────────────────────────────
    file_where: dict[str, Any] = {"granularity": {"$eq": "file"}}
    if language_filter:
        file_where = {
            "$and": [
                {"granularity": {"$eq": "file"}},
                {"language": {"$eq": language_filter}},
            ]
        }

    file_output: list[dict[str, Any]] = []
    top_file_paths: list[str] = []
    try:
        file_results = collection.query(
            query_embeddings=[embedding],
            n_results=min(n_files, count),
            where=file_where,
            include=["documents", "metadatas", "distances"],
        )
        if file_results and file_results.get("documents"):
            for doc, meta, dist in zip(
                file_results["documents"][0],
                file_results["metadatas"][0],
                file_results["distances"][0],
            ):
                file_output.append({"source": doc, "metadata": meta, "distance": dist})
                fp = meta.get("file_path", "")
                if fp:
                    top_file_paths.append(fp)
    except Exception:
        pass

    # ── Stage 2: function-level chunks within the top files ───────────────────
    func_output: list[dict[str, Any]] = []
    if top_file_paths:
        func_conditions: list[dict] = [
            {"granularity": {"$eq": "function"}},
            {"file_path": {"$in": top_file_paths}},
        ]
        if language_filter:
            func_conditions.append({"language": {"$eq": language_filter}})
        func_where: dict[str, Any] = {"$and": func_conditions}

        try:
            func_results = collection.query(
                query_embeddings=[embedding],
                n_results=min(n_functions, count),
                where=func_where,
                include=["documents", "metadatas", "distances"],
            )
            if func_results and func_results.get("documents"):
                for doc, meta, dist in zip(
                    func_results["documents"][0],
                    func_results["metadatas"][0],
                    func_results["distances"][0],
                ):
                    func_output.append({"source": doc, "metadata": meta, "distance": dist})
        except Exception:
            pass

    return {"files": file_output, "functions": func_output}


def delete_collection(user_id: str, repo_name: str) -> None:
    """Remove a repo's embeddings from ChromaDB."""
    client = _get_client()
    col_name = _collection_name(user_id, repo_name)
    try:
        client.delete_collection(col_name)
    except Exception:
        pass


def delete_guest_collections(guest_session_id: str) -> int:
    """
    Delete all ChromaDB collections that belong to a guest session.
    Collections created by embed_and_store store the user_id in their metadata,
    so we can do an exact match to find all collections for this guest.
    Returns the number of deleted collections.
    """
    client = _get_client()
    deleted = 0
    try:
        all_collections = client.list_collections()
        for col in all_collections:
            name = col.name if hasattr(col, "name") else str(col)
            try:
                collection = client.get_collection(name)
                meta = collection.metadata or {}
                if meta.get("user_id") == guest_session_id:
                    client.delete_collection(name)
                    deleted += 1
                    logger.info("Deleted guest collection: %s", name)
            except Exception:
                continue
    except Exception as e:
        logger.warning("delete_guest_collections error: %s", e)
    return deleted
