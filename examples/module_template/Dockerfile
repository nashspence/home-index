FROM python:3.11.13-slim
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ARG HOME_INDEX_REF=main
RUN pip install --no-cache-dir \
    git+https://github.com/nashspence/home-index.git@${HOME_INDEX_REF}
COPY main.py .
ENTRYPOINT ["python3", "/app/main.py"]
