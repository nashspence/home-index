FROM python:alpine

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    attr \
    file \
    git \
    tzdata \
    && apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py .
ENTRYPOINT ["python3", "/app/main.py"]
