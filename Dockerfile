FROM python:3.11.13-slim

ARG COMMIT_SHA=unknown
ENV COMMIT_SHA=${COMMIT_SHA}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libmagic-mgc \
    tzdata \
    && rm -rf /var/lib/apt/lists/*


ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

RUN pip install --no-cache-dir --disable-pip-version-check \
    apscheduler==3.11.0 \
    debugpy==1.8.14 \
    meilisearch-python-sdk==4.7.1 \
    python-magic==0.4.27 \
    langchain-core==0.1.48 \
    langchain-text-splitters==0.0.1 \
    transformers==4.53.0 \
    tiktoken==0.6.0 \
    redis==5.0.4 \
    PyYAML==6.0.1 \
    xxhash==3.5.0 \
    fastapi==0.116.1 \
    asgiwebdav==1.5.0 \
    uvicorn==0.35.0 \
    aiofiles==23.2.1 \
    httpx==0.28.1 \
    types-PyYAML==6.0.12

COPY main.py ./
COPY shared ./shared
COPY features ./features
ENTRYPOINT ["python3", "main.py"]
