FROM python:3.11-slim

# Install AIPerf for performance benchmarking
# Install Datadog for metrics export (Custom Metrics API)
#
# NOTE: these are intentionally unpinned upstream, so an image rebuilt tomorrow
# may not contain the same code as the one running today, and a compromised
# release would be pulled in automatically. Pinning requires resolving the exact
# versions against PyPI (`pip install aiperf==X.Y.Z datadog==A.B.C`), which needs
# network access this change does not have; recorded here as the next step.
RUN pip install --no-cache-dir aiperf datadog

WORKDIR /scripts

# Copy common utilities (from repo root)
COPY common/ /scripts/common/

# Copy benchmark script (from repo root)
COPY aiperf/benchmark.py /scripts/benchmark.py
RUN chmod +x /scripts/benchmark.py

# The image ran as root: the benchmark needs no privileges, but any code-execution
# bug in it (or in a dependency) started as uid 0 inside the container, which is
# the precondition for most container escapes. A dedicated unprivileged account is
# created instead. The GID is matched by `fsGroup` in cronjob.yaml so the mounted
# results volume stays writable.
RUN groupadd --gid 10001 benchmark \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin benchmark \
    && chown -R benchmark:benchmark /scripts
USER 10001:10001

CMD ["python3", "/scripts/benchmark.py"]
