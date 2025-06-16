FROM python:3.11-alpine
ENV PYTHONUNBUFFERED=1
RUN apk add --no-cache \
    attr \
    file \
    git \
    tzdata
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
ENTRYPOINT ["python3", "/app/main.py"]
