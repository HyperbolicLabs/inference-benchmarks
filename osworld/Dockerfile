# Multi-stage build for better caching and smaller image
FROM python:3.11-slim as builder

# Install build dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /osworld

# Clone OSWorld repository (cached layer - only rebuilds if OSWORLD_VERSION changes)
# Use shallow clone with better error handling
ARG OSWORLD_VERSION=main
RUN git clone --depth 1 --branch ${OSWORLD_VERSION} https://github.com/xlang-ai/OSWorld.git /osworld 2>&1 || \
    (echo "Shallow clone failed, trying full clone..." && \
     git clone https://github.com/xlang-ai/OSWorld.git /osworld && \
     cd /osworld && git checkout ${OSWORLD_VERSION} 2>/dev/null || git checkout -b ${OSWORLD_VERSION} || true)

# Install Python dependencies in optimal order to avoid conflicts:
# 1. Upgrade pip (changes rarely)
# 2. Install OSWorld FIRST - let it resolve all its dependencies (avoids uninstall/reinstall)
# 3. Install our additional packages on top (datadog, ddtrace) - these don't conflict
# This prevents OSWorld from uninstalling/reinstalling packages we pre-installed
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e /osworld && \
    pip install --no-cache-dir \
    datadog \
    ddtrace

# Cleanup: Remove unnecessary files to reduce image size
# Remove git history, tests, docs, and other development files
# IMPORTANT: Preserve evaluation_examples/examples/ directory (contains task JSON files)
RUN find /osworld -type d -name ".git" -exec rm -rf {} + 2>/dev/null || true && \
    find /osworld -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /osworld -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true && \
    find /osworld -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /osworld -type f -name "*.pyo" -delete 2>/dev/null || true && \
    find /osworld -type d \( -name "tests" -o -name "test" -o -name "docs" -o -name ".github" \) -exec rm -rf {} + 2>/dev/null || true && \
    # Remove examples directories but NOT evaluation_examples/examples/ (contains task files)
    find /osworld -type d -name "examples" ! -path "*/evaluation_examples/examples*" -exec rm -rf {} + 2>/dev/null || true

# Final stage - minimal runtime image
FROM python:3.11-slim

# Install runtime dependencies in a single layer
# Group by update frequency: system libs (rarely change) then Docker (changes more often)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Graphics libraries (required for OSWorld GUI)
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    # Docker (for Docker provider support in containerd/cri-o clusters)
    # docker.io provides dockerd (daemon) but may not include docker CLI
    # Install docker.io for daemon, then try to get docker CLI
    docker.io \
    && (docker --version 2>/dev/null || \
        (echo "docker CLI not found, checking for docker-cli package..." && \
         apt-get update && \
         (apt-get install -y --no-install-recommends docker-cli 2>/dev/null || \
          echo "docker-cli not available in repos")) || true) \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && (docker --version 2>&1 || echo "⚠️  docker CLI not available after installation")

# Copy Python packages from builder (single layer)
# Only copy what's needed - site-packages and bin
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy OSWorld installation (changes when OSWorld updates)
# Exclude unnecessary files already cleaned in builder stage
COPY --from=builder /osworld /osworld

# Copy application files and set permissions in a single layer
# Order: least frequently changing files first for better cache hits
COPY common/ /osworld/common/
COPY osworld/run_evaluation.py osworld/run_with_ddtrace.py /osworld/
RUN chmod +x /osworld/run_evaluation.py /osworld/run_with_ddtrace.py && \
    mkdir -p /osworld/results /osworld/logs /osworld/evaluation_examples && \
    # Ensure directories have correct permissions
    chmod -R 755 /osworld/results /osworld/logs /osworld/evaluation_examples

# Set environment variables (single layer)
ENV PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /osworld

# Default command (can be overridden)
CMD ["python3", "run_multienv_qwen3vl.py", "--help"]
