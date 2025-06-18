FROM python:3.11.13-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    attr \
    file \
    git \
    libmagic1 \
    tzdata \
    shared-mime-info \
    && apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN python - <<'EOF'
from transformers import AutoTokenizer
from sentence_transformers import SentenceTransformer
AutoTokenizer.from_pretrained("intfloat/e5-small-v2")
SentenceTransformer("intfloat/e5-small-v2")
EOF

COPY packages/home_index .
ENTRYPOINT ["python3", "/app/main.py"]
