# Use a lightweight Python image
FROM python:3.11-slim

# Set environment variables for security and performance
ENV PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Set working directory
WORKDIR /app

# Install dependencies in a virtual environment to keep the base clean
COPY requirements.txt /app/
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy application code after installing dependencies (prevents cache busting)
COPY . /app/

# Use non-root user for security
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

# Expose FastAPI default port
EXPOSE 8000

# Set entrypoint using the virtual environment
CMD ["/opt/venv/bin/uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
