FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application code
COPY planning_agent/ planning_agent/
COPY web/ web/
COPY cli/ cli/

# Create data directory for SQLite
RUN mkdir -p /app/data

# Set environment variables (credentials and settings passed at deploy time)
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///./data/planning_agent.db

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Run web server
CMD ["python", "-m", "web.server"]
