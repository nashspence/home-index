FROM python:3.11.13-alpine
ENV PYTHONUNBUFFERED=1
RUN apk add --no-cache \
    tzdata
WORKDIR /app
RUN pip install --no-cache-dir \
    git+https://github.com/nashspence/home-index.git@1e5a67cb90465abf1c8e0885c7614c9e28314660
COPY main.py .
ENTRYPOINT ["python3", "/app/main.py"]
