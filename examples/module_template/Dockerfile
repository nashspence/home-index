FROM python:3.11.13-alpine
ENV PYTHONUNBUFFERED=1
RUN apk add --no-cache \
    git \
    tzdata
WORKDIR /app
ARG HOME_INDEX_REF=main
RUN pip install --no-cache-dir \
    git+https://github.com/nashspence/home-index.git@${HOME_INDEX_REF}
COPY main.py .
ENTRYPOINT ["python3", "/app/main.py"]
