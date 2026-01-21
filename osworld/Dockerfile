# Multi-stage build for better caching and smaller image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /osworld

# Clone OSWorld repository (cached layer)
ARG OSWORLD_VERSION=main
RUN git clone --depth 1 --branch ${OSWORLD_VERSION} https://github.com/xlang-ai/OSWorld.git /osworld || \
    (git clone https://github.com/xlang-ai/OSWorld.git /osworld && \
     cd /osworld && git checkout ${OSWORLD_VERSION} 2>/dev/null || true)

# Install Python dependencies (cached layer)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    openai \
    pillow \
    numpy \
    pyautogui \
    python-dotenv \
    datadog \
    ddtrace \
    && pip install --no-cache-dir -e /osworld

# Final stage - copy only what's needed
FROM python:3.11-slim

# Install runtime dependencies only
# Note: libgl1-mesa-glx is not available in Debian Bookworm, use libgl1 instead
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy OSWorld installation from builder
COPY --from=builder /osworld /osworld
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy common utilities (from repo root)
COPY common/ /osworld/common/

# Copy evaluation runner script (from repo root)
COPY osworld/run_evaluation.py /osworld/run_evaluation.py
RUN chmod +x /osworld/run_evaluation.py

# Copy ddtrace wrapper script (from repo root)
COPY osworld/run_with_ddtrace.py /osworld/run_with_ddtrace.py
RUN chmod +x /osworld/run_with_ddtrace.py

# Create directories for results and logs
RUN mkdir -p /osworld/results /osworld/logs /osworld/evaluation_examples

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TOKENIZERS_PARALLELISM=false

WORKDIR /osworld

# Default command (can be overridden)
CMD ["python3", "run_multienv_qwen3vl.py", "--help"]
