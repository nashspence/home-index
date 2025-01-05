FROM python:alpine

# Set non-interactive for apk (though it doesn't require DEBIAN_FRONTEND)
ENV PYTHONUNBUFFERED=1

# Install necessary packages using apk
RUN apk add --no-cache \
    attr \
    file \
    git \
    tzdata

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main application file
COPY main.py .

# Set the entry point for the container
ENTRYPOINT ["python3", "/app/main.py"]
