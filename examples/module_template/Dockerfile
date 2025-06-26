FROM python:3.11.13-alpine
ENV PYTHONUNBUFFERED=1
RUN apk add --no-cache tzdata
WORKDIR /app

# Install Home Index from the local source tree so the example module
# always matches the version under test.
COPY . /src
RUN pip install --no-cache-dir /src

# Copy the module entrypoint
COPY examples/module_template/main.py ./main.py

ENTRYPOINT ["python3", "/app/main.py"]
