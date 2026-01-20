# Inference Benchmarks

Benchmark tools for testing and evaluating inference endpoints.

## Overview

This repository contains benchmark tools for testing inference endpoints:
- **AIPerf**: Performance benchmarking (latency, throughput)
- **OSWorld**: End-to-end agent evaluation

Both benchmarks automatically export metrics to Datadog.

## Structure

```
inference-benchmarks/
├── common/                # Shared components
│   ├── datadog_utils.py  # Common Datadog export logic
│   └── Makefile.common   # Common Makefile functions
│
├── aiperf/               # AIPerf performance benchmarking
│   ├── benchmark.py
│   ├── Dockerfile
│   ├── Makefile
│   ├── cronjob.yaml
│   ├── job.yaml
│   ├── pvc.yaml
│   └── README.md
│
├── osworld/              # OSWorld evaluation
│   ├── run_evaluation.py
│   ├── Dockerfile
│   ├── Makefile
│   ├── osworld-job.yaml
│   ├── pvc.yaml
│   └── README.md
│
├── Makefile              # Root Makefile (builds all)
└── README.md
```

## Common Components

### `common/datadog_utils.py`

Shared Datadog export utilities used by all benchmarks:
- Retry logic with exponential backoff
- Batch sending (20 metrics per batch)
- Async (non-blocking) support
- Partial success handling

**Usage:**
```python
from datadog_utils import send_metrics_async

metrics = {"latency_p95": 150.5, "throughput": 100.2}
base_tags = ["model:Qwen/Qwen3-VL-32B-Thinking", "cluster_name:inference-cluster"]

send_metrics_async(
    metrics=metrics,
    metric_prefix="inference.benchmark.aiperf",
    base_tags=base_tags
)
```

## Quick Start

### AIPerf

```bash
cd aiperf
make build-push    # Build and push image
make deploy        # Deploy CronJob
```

See `aiperf/README.md` for details.

### OSWorld

```bash
cd osworld
make build-push    # Build and push image
make deploy        # Deploy evaluation job
```

See `osworld/README.md` for details.

## Building All

```bash
# Build all benchmarks
cd aiperf && make build && cd ../osworld && make build

# Or individually
cd aiperf && make build-push
cd osworld && make build-push
```

## Datadog Metrics

All benchmarks send metrics to Datadog with prefix:
- AIPerf: `inference.benchmark.aiperf.*`
- OSWorld: `inference.benchmark.osworld.*`

**Required:** Set `DD_API_KEY` environment variable or Kubernetes secret.

## Requirements

- Kubernetes cluster
- Datadog API key (optional, for metrics export)
- GitHub Container Registry access (for images)

## Adding a New Benchmark

1. Create directory: `mkdir new-benchmark`
2. Create script that uses `common/datadog_utils.py`
3. Create Dockerfile, Makefile, Kubernetes manifests
4. Follow patterns from existing benchmarks

## License

[Your License Here]
