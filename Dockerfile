FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source
COPY . .

# Create data directory
RUN mkdir -p data

EXPOSE 8080

# Default: start dashboard (override with `docker run ... firm trade`)
CMD ["python", "-m", "src.cli", "dashboard", "--host", "0.0.0.0", "--port", "8080"]
