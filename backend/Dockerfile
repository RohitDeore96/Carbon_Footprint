# Stage 1: Builder
FROM python:3.11-slim AS builder

# Install compiler tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Generate Python wheels
COPY requirements.txt .
RUN pip install --upgrade pip --no-cache-dir \
    && pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt

# Copy the app layer to Builder stage so Runner can copy it from here
COPY app/ ./app/

# Stage 2: Runner
FROM python:3.11-slim AS runner

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Security Constraint: run as a non-root user
RUN useradd -m appuser

WORKDIR /app

# Copy ONLY the built wheels and app layer from the Builder stage
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
    && rm -rf /wheels

COPY --from=builder /app/app ./app

# Set correct ownership
RUN chown -R appuser:appuser /app

# Run as non-root
USER appuser

# Expose Port 8080 (Cloud Run requirement)
EXPOSE 8080

# Explicit HEALTHCHECK
HEALTHCHECK CMD curl --fail http://localhost:8080/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
