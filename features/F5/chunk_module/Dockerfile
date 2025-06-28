ARG HOME_INDEX_IMAGE=ghcr.io/nashspence/home-index:latest
FROM ${HOME_INDEX_IMAGE}
WORKDIR /app
COPY main.py /app/chunk_module/main.py
ENTRYPOINT ["python3", "/app/chunk_module/main.py"]
