FROM python:3.11.13-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libmagic-mgc \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# ── *Optional* CUDA user-space install (skipped when CUDA_MAJOR=0) ──────────
ARG CUDA_MAJOR=0
ARG CUDA_MINOR=0
ARG CUDA_PKG
RUN set -eux; \
    if [ "${CUDA_MAJOR}" != "0" ]; then \
        CUDA_PKG="${CUDA_PKG:-${CUDA_MAJOR}-${CUDA_MINOR}}"; \
        UBUNTU_REL=$(lsb_release -sr | tr -d .); \
        curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu${UBUNTU_REL}/x86_64/cuda-ubuntu${UBUNTU_REL}.pin \
          -o /etc/apt/preferences.d/cuda-repository-pin-600; \
        curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu${UBUNTU_REL}/x86_64/3bf863cc.pub | \
          gpg --dearmor -o /usr/share/keyrings/cuda.gpg; \
        echo "deb [signed-by=/usr/share/keyrings/cuda.gpg] https://developer.download.nvidia.com/compute/cuda/repos/ubuntu${UBUNTU_REL}/x86_64/ /" \
          > /etc/apt/sources.list.d/cuda.list; \
        apt-get update; \
        apt-get install -y --no-install-recommends \
            cuda-toolkit-${CUDA_PKG} \
            cuda-compat-${CUDA_PKG}; \
        rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app

RUN pip install --no-cache-dir \
    apscheduler==3.11.0 \
    debugpy==1.8.14 \
    meilisearch-python-sdk==4.7.1 \
    python-magic==0.4.27 \
    xxhash==3.5.0 \
    sentence-transformers==4.1.0 \
    transformers==4.52.4
RUN python - <<'EOF'
from transformers import AutoTokenizer
from sentence_transformers import SentenceTransformer
AutoTokenizer.from_pretrained("intfloat/e5-small-v2")
SentenceTransformer("intfloat/e5-small-v2")
EOF

COPY packages/home_index ./
COPY features ./features
ENTRYPOINT ["python3", "/app/main.py"]
