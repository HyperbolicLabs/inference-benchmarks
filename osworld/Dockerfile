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
     cd /osworld && git checkout ${OSWORLD_VERSION} 2>/dev/null || git checkout -b ${OSWORLD_VERSION} || true) && \
    # Remove git history immediately to save space
    rm -rf /osworld/.git /osworld/.github 2>/dev/null || true

# Fix lib_run_single.py to handle agents that don't support vm_ip parameter
# Update the fallback pattern to gracefully handle different agent reset() signatures
RUN python3 << 'EOF'
file_path = '/osworld/lib_run_single.py'
with open(file_path, 'r') as f:
    lines = f.readlines()

# Find and replace the problematic reset call pattern
new_lines = []
i = 0
while i < len(lines):
    # Look for the pattern: "# Reset agent with fresh VM IP"
    if i < len(lines) - 4 and "Reset agent with fresh VM IP" in lines[i]:
        # Check if this is the problematic pattern
        if i + 3 < len(lines) and "agent.reset(runtime_logger, vm_ip=env.vm_ip)" in lines[i+2]:
            if i + 4 < len(lines) and "agent.reset(vm_ip=env.vm_ip)" in lines[i+4]:
                # Replace with better fallback pattern
                new_lines.append(lines[i])  # Keep the comment
                new_lines.append("    # Handle agent reset signature differences gracefully\n")
                new_lines.append("    try:\n")
                new_lines.append("        agent.reset(runtime_logger, vm_ip=env.vm_ip)\n")
                new_lines.append("    except Exception:\n")
                new_lines.append("        try:\n")
                new_lines.append("            agent.reset(runtime_logger)\n")
                new_lines.append("        except Exception:\n")
                new_lines.append("            agent.reset()\n")
                i += 5  # Skip the old 5 lines
                continue
    new_lines.append(lines[i])
    i += 1

with open(file_path, 'w') as f:
    f.writelines(new_lines)
print("✅ Patched lib_run_single.py to handle agents without vm_ip support")
EOF

# Install Python dependencies in optimal order to avoid conflicts:
# 1. Upgrade pip (changes rarely)
# 2. Install OSWorld FIRST - let it resolve all its dependencies (avoids uninstall/reinstall)
# 3. Install our additional packages on top (datadog, ddtrace) - these don't conflict
# This prevents OSWorld from uninstalling/reinstalling packages we pre-installed
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e /osworld && \
    pip install --no-cache-dir \
    datadog \
    ddtrace && \
    # Clean up pip cache and temporary files immediately
    pip cache purge 2>/dev/null || true && \
    rm -rf /tmp/* /var/tmp/* /root/.cache/pip 2>/dev/null || true

# Pre-download and extract OSWorld VM image to save runtime (saves ~3-4 minutes per run)
# VM image: 11.4GB Ubuntu.qcow2.zip from HuggingFace
# This is done in builder stage to leverage build cache and avoid runtime download
# OSWorld checks if Ubuntu.qcow2 exists before downloading, so pre-extracting it skips the download
# Note: This is the largest part of the image (~11.4GB), but required for runtime
RUN pip install --no-cache-dir --no-warn-script-location requests tqdm && \
    mkdir -p /osworld/docker_vm_data && \
    cd /osworld/docker_vm_data && \
    echo "Pre-downloading OSWorld VM image (11.4GB)..." && \
    python3 << 'EOF'
import requests
import zipfile
import os
from tqdm import tqdm

url = 'https://huggingface.co/datasets/xlangai/ubuntu_osworld/resolve/main/Ubuntu.qcow2.zip'
zip_path = 'Ubuntu.qcow2.zip'
vm_path = 'Ubuntu.qcow2'

if not os.path.exists(vm_path):
    print(f'Downloading {url}...')
    r = requests.get(url, stream=True)
    r.raise_for_status()
    total = int(r.headers.get('content-length', 0))
    
    with open(zip_path, 'wb') as f, tqdm(total=total, unit='B', unit_scale=True, desc='Download') as pbar:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                pbar.update(len(chunk))
    
    print('Extracting...')
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall('.')
    
    os.remove(zip_path)
    print(f'VM image ready: {vm_path}')
    print(f'Size: {os.path.getsize(vm_path) / (1024**3):.2f} GB')
else:
    print(f'VM image already exists: {vm_path}')
EOF

# Clean up download tools and temporary files immediately after VM download
# Uninstall packages to save space (they're only needed for download)
RUN pip uninstall -y requests tqdm 2>/dev/null || true && \
    pip cache purge 2>/dev/null || true && \
    # Aggressive cleanup of all temporary and cache files
    rm -rf /tmp/* /var/tmp/* /root/.cache/* /root/.local/share/pip 2>/dev/null || true && \
    # Clean up any Python bytecode that might have been generated
    find /osworld -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /osworld -type f -name "*.pyc" -delete 2>/dev/null || true

# Cleanup: Remove unnecessary files to reduce image size
# Remove git history, tests, docs, and other development files
# IMPORTANT: Preserve evaluation_examples/examples/ directory (contains task JSON files)
RUN find /osworld -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /osworld -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true && \
    find /osworld -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /osworld -type f -name "*.pyo" -delete 2>/dev/null || true && \
    find /osworld -type d \( -name "tests" -o -name "test" -o -name "docs" -o -name ".github" \) -exec rm -rf {} + 2>/dev/null || true && \
    # Remove examples directories but NOT evaluation_examples/examples/ (contains task files)
    find /osworld -type d -name "examples" ! -path "*/evaluation_examples/examples*" -exec rm -rf {} + 2>/dev/null || true && \
    # Remove documentation files
    find /osworld -type f \( -name "*.md" -o -name "LICENSE" -o -name "CONTRIBUTING*" -o -name "CHANGELOG*" \) ! -path "*/evaluation_examples/*" -delete 2>/dev/null || true && \
    # Remove large unnecessary files
    find /osworld -type f -name "*.zip" ! -path "*/docker_vm_data/*" -delete 2>/dev/null || true && \
    find /osworld -type f -name "*.tar.gz" ! -path "*/docker_vm_data/*" -delete 2>/dev/null || true && \
    # Final cleanup of temporary files
    rm -rf /tmp/* /var/tmp/* /root/.cache 2>/dev/null || true

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
    && rm -rf /var/cache/apt/archives/* \
    && (docker --version 2>&1 || echo "⚠️  docker CLI not available after installation")

# Copy Python packages from builder (single layer)
# Only copy what's needed - site-packages and bin
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy OSWorld installation (changes when OSWorld updates)
# Exclude unnecessary files already cleaned in builder stage
# Use --chown to avoid permission issues and reduce layers
COPY --from=builder --chown=root:root /osworld /osworld

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
