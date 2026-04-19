FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Upgrade pip and install uv for fast package management
RUN pip install --upgrade pip && \
    pip install uv

# Copy dependency files and README (required by pyproject.toml)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies using uv
RUN uv pip install --system -e .

# Copy application code
COPY . /app

# Expose HTTP port
EXPOSE 8000

# Run the server in HTTP mode by default
CMD ["python", "-m", "consensus_mcp.server", "--http"]
