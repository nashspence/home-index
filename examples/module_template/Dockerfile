FROM python:3.11.13-alpine
ENV PYTHONUNBUFFERED=1
RUN apk add --no-cache \
    attr \
    file \
    tzdata
WORKDIR /app
COPY examples/module_template/requirements.txt ./requirements.txt
COPY setup.py ./setup.py
COPY packages ./packages
RUN pip install --no-cache-dir . -r requirements.txt
COPY examples/module_template/main.py ./main.py
ENTRYPOINT ["python3", "/app/main.py"]
