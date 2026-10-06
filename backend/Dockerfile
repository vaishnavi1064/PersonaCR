# PersonaCR backend — local/dev image for minikube (not production-hardened).
# Build from repo:  docker build -t personacr-backend ./backend
# Or with minikube's Docker:  minikube docker-env | Invoke-Expression  (PowerShell)

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# System deps occasionally needed by scientific / onnx wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# CPU-only torch. sentence-transformers (STS scoring) pulls torch; the default
# Linux wheel is the CUDA build (+~4 GB of nvidia-*/triton wheels) that nothing
# here can use. Installing the CPU wheel first satisfies that requirement, and
# the check fails the build if a CUDA package sneaks back in. Keep the version
# equal to what requirements.txt resolves.
ARG TORCH_VERSION=2.14.1
RUN pip install --no-cache-dir "torch==${TORCH_VERSION}" --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
    && if pip list 2>/dev/null | grep -iE '^(nvidia|triton|cuda)'; then echo "CUDA packages found — expected CPU-only torch" >&2; exit 1; fi

COPY . /app/backend/

# Ensure import path `backend.src.main` resolves (namespace package safety)
RUN touch /app/backend/__init__.py \
    && touch /app/backend/src/__init__.py

# Embedded Chroma PersistentClient path (mount a PVC here in k8s)
RUN mkdir -p /app/backend/.chroma

EXPOSE 8000

# /health exists on the FastAPI app (see backend/src/main.py)
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
