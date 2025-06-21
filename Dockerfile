FROM python:3.11.13-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    attr \
    file \
    git \
    libmagic1 \
    libmagic-mgc \
    tzdata \
    shared-mime-info \
    && apt-get clean

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

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN python - <<'EOF'
from transformers import AutoTokenizer
from sentence_transformers import SentenceTransformer
AutoTokenizer.from_pretrained("intfloat/e5-small-v2")
SentenceTransformer("intfloat/e5-small-v2")
EOF

COPY packages/home_index ./
COPY features ./features
ENTRYPOINT ["python3", "/app/main.py"]
