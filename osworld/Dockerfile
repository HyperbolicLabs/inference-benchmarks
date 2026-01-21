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
ARG OSWORLD_VERSION=main
RUN git clone --depth 1 --branch ${OSWORLD_VERSION} https://github.com/xlang-ai/OSWorld.git /osworld || \
    (git clone https://github.com/xlang-ai/OSWorld.git /osworld && \
     cd /osworld && git checkout ${OSWORLD_VERSION} 2>/dev/null || true)

# Install Python dependencies in optimal order for caching:
# 1. Upgrade pip (changes rarely)
# 2. Install common dependencies (changes less frequently)
# 3. Install OSWorld (changes most frequently)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    openai \
    pillow \
    numpy \
    pyautogui \
    python-dotenv \
    datadog \
    ddtrace && \
    pip install --no-cache-dir -e /osworld

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
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder (single layer)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy OSWorld installation (changes when OSWorld updates)
COPY --from=builder /osworld /osworld

# Copy application files and set permissions in a single layer
# Order: least frequently changing files first for better cache hits
COPY common/ /osworld/common/
COPY osworld/run_evaluation.py osworld/run_with_ddtrace.py /osworld/
RUN chmod +x /osworld/run_evaluation.py /osworld/run_with_ddtrace.py && \
    mkdir -p /osworld/results /osworld/logs /osworld/evaluation_examples

# Set environment variables (single layer)
ENV PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /osworld

# Default command (can be overridden)
CMD ["python3", "run_multienv_qwen3vl.py", "--help"]
