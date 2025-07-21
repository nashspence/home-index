FROM python:3.11.13-slim
ENV PYTHONUNBUFFERED=1
ENV METADATA_DIRECTORY=/home-index/metadata
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ARG COMMIT_SHA=main
ENV COMMIT_SHA=${COMMIT_SHA}
RUN pip install --no-cache-dir \
    redis==5.0.4 \
    PyYAML==6.0.1
RUN pip install --no-deps --no-cache-dir \
    git+https://github.com/nashspence/home-index.git@${COMMIT_SHA}

