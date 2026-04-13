FROM docker.m.daocloud.io/library/python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# 1. Use a faster mirror for apt-get (resolved network issues in China)
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 2. Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# 3. Use a faster mirror for pip and upgrade build tools
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir --upgrade pip setuptools wheel

# 3.1 Install MCP adapter explicitly so backend startup can load MCP tools reliably
RUN pip install --no-cache-dir "langchain-mcp-adapters>=0.1.0"

# 4. Copy configuration first to leverage Docker cache
COPY pyproject.toml .

# 5. Pre-install dependencies
RUN pip install --no-cache-dir . || true

# 6. Copy the rest of the application code
COPY . .

# 7. Final installation in non-editable mode
RUN pip install --no-cache-dir .

# Expose the API port
EXPOSE 8000

# Run the application
CMD ["python", "run_api.py"]
