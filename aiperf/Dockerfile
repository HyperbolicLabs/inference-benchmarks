FROM python:3.11-slim

# Install AIPerf for performance benchmarking
# Install Datadog for metrics export
RUN pip install --no-cache-dir aiperf datadog

WORKDIR /scripts

# Copy common utilities (from repo root)
COPY common/ /scripts/common/

# Copy benchmark script (from repo root)
COPY aiperf/benchmark.py /scripts/benchmark.py
RUN chmod +x /scripts/benchmark.py

CMD ["python3", "/scripts/benchmark.py"]
