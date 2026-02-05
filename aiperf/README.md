# AIPerf Benchmark Script

This directory contains the AIPerf benchmarking setup for the inference endpoints.

## Overview

The benchmark script runs performance tests against the inference API endpoint using AIPerf. **API gateway (default):** benchmarks target `api.hyperbolic.xyz` for full-stack overhead; set `ENDPOINT_URL` to `https://api.hyperbolic.xyz/v1/chat/completions` and use API key auth (`OPENAI_API_KEY`). It supports:
- API key authentication (Bearer) for api.hyperbolic.xyz
- Cloudflare Access for inference.hyperbolic.xyz (optional)
- Configurable concurrency and request counts
- Streaming and non-streaming modes
- Duration-based or count-based benchmarking

## Files

- `benchmark.py` - Main benchmark script
- `Dockerfile` - Docker image definition
- `cronjob.yaml` - Kubernetes CronJob configuration
- `Makefile` - Build and deployment automation
- `create-secret.sh` - Script to create Kubernetes secret for credentials

## Quick Start

### 1. Build and Push Docker Image

```bash
cd scripts/aiperf

# Build the image
make build

# Push to registry (requires GITHUB_TOKEN)
export GITHUB_TOKEN=your_token
make push

# Or do both at once
make build-push
```

### 2. Create Kubernetes Secret for Credentials

The CronJob uses **api.hyperbolic.xyz** by default and requires an API key (get from dashboard / sign up).

**API key (api.hyperbolic.xyz, default):**
```bash
# From env (recommended; key never touches disk)
OPENAI_API_KEY=your-key ./create-api-key-secret.sh

# Or with kubectl (replace YOUR_API_KEY)
kubectl create secret generic hyperbolic-api-key \
  --from-literal=api-key="YOUR_API_KEY" \
  -n inference-benchmark
```

**Optional: Cloudflare Access (inference.hyperbolic.xyz):**

**Option A: Using Makefile**
```bash
make create-secret CLIENT_ID=your-client-id CLIENT_SECRET=your-client-secret
```

**Option B: Using Script**
```bash
./create-secret.sh CLIENT_ID CLIENT_SECRET [NAMESPACE]
```

**Option C: From Credentials File**
If you have `cloudflare-access-credentials.txt` in the repo root:
```bash
./create-secret.sh
```

**Option D: Manual kubectl**
```bash
kubectl create secret generic cloudflare-access-credentials \
  --from-literal=client-id="YOUR_CLIENT_ID" \
  --from-literal=client-secret="YOUR_CLIENT_SECRET" \
  -n inference-benchmark
```

### 3. Deploy CronJob

```bash
make deploy
```

## How Credentials Are Passed

### In Kubernetes (CronJob)

The CronJob uses **api.hyperbolic.xyz** and reads the API key from a secret:

```yaml
env:
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: hyperbolic-api-key
        key: api-key
        optional: true
```

**Secret (api.hyperbolic.xyz):**
- Name: `hyperbolic-api-key`
- Namespace: `inference-benchmark` (default)
- Keys: `api-key` — your API key from the dashboard

Optional Cloudflare Access (for inference.hyperbolic.xyz):

```yaml
  - name: CF_ACCESS_CLIENT_ID
    valueFrom:
      secretKeyRef:
        name: cloudflare-access-credentials
        key: client-id
        optional: true
  - name: CF_ACCESS_CLIENT_SECRET
    valueFrom:
      secretKeyRef:
        name: cloudflare-access-credentials
        key: client-secret
        optional: true
```

### Locally (Testing)

For **api.hyperbolic.xyz** (default):

```bash
export OPENAI_API_KEY="your-api-key"
python3 benchmark.py
```

For **inference.hyperbolic.xyz** (Cloudflare Access):

```bash
export CF_ACCESS_CLIENT_ID="your-client-id"
export CF_ACCESS_CLIENT_SECRET="your-client-secret"
export ENDPOINT_URL="https://inference.hyperbolic.xyz/v1/chat/completions/qwen3-vl-32b"
python3 benchmark.py
```

Or use a credentials file for Cloudflare Access:

```bash
# Create cloudflare-access-credentials.txt
cat > cloudflare-access-credentials.txt <<EOF
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
EOF

# Source and run
source cloudflare-access-credentials.txt
export ENDPOINT_URL="https://inference.hyperbolic.xyz/v1/chat/completions/qwen3-vl-32b"
python3 benchmark.py
```

## Configuration

### Environment Variables

The benchmark script supports these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `Qwen/Qwen3-VL-32B-Thinking` | HuggingFace model id (AIPerf validates this; use full id, e.g. `Qwen/Qwen2.5-7B-Instruct` for 8b) |
| `ENDPOINT_URL` | `https://api.hyperbolic.xyz/v1/chat/completions` | Chat endpoint URL (model passed in request body) |
| `ENDPOINT_TYPE` | `chat` | Endpoint type (chat/completions/embeddings) |
| `CONCURRENCY` | `10` | Number of concurrent requests |
| `REQUEST_COUNT` | `100` | Total number of requests |
| `STREAMING` | `true` | Enable streaming responses |
| `OUTPUT_DIR` | `/tmp/aiperf-results` | Results directory |
| `OPENAI_API_KEY` or `HYPERBOLIC_API_KEY` | - | API key for Bearer auth (api.hyperbolic.xyz) |
| `CF_ACCESS_CLIENT_ID` | - | Cloudflare Access Client ID (optional, inference.hyperbolic.xyz) |
| `CF_ACCESS_CLIENT_SECRET` | - | Cloudflare Access Client Secret (optional) |
| `REQUEST_TIMEOUT` | - | Request timeout in seconds (optional) |
| `OUTPUT_TOKENS_MEAN` | - | Mean output tokens per response (optional) |
| `BENCHMARK_DURATION` | - | Benchmark duration in seconds (optional) |
| `BENCHMARK_GRACE_PERIOD` | - | Grace period after benchmark ends (optional) |

### CronJob Configuration

Two **staggered** CronJobs run sequentially (no parallel load on the backend):

| CronJob | Endpoint | Schedule |
|---------|----------|----------|
| `aiperf-benchmark-api` | https://api.hyperbolic.xyz | `0,20,40 * * * *` (:00, :20, :40) |
| `aiperf-benchmark-inference` | https://inference.hyperbolic.ai | `10,30,50 * * * *` (:10, :30, :50) |

- **Duration**: 8 minutes per benchmark
- **Concurrency**: 1 (avoids 429s from api.hyperbolic.xyz/Cloudflare)
- **Timeout**: 60 seconds per request
- **Output Tokens**: Mean of 50 tokens per response

In Datadog, use the **endpoint** template variable to filter by `https://api.hyperbolic.xyz` or `https://inference.hyperbolic.ai`.

## Makefile Targets

```bash
make help              # Show help message
make build             # Build Docker image
make push              # Build and push image (requires login)
make login             # Login to GitHub Container Registry
make build-push         # Login, build, and push
make create-secret      # Create Kubernetes secret for credentials
make deploy            # Deploy CronJob to Kubernetes
```

## Troubleshooting

### Secret Not Found

If the CronJob fails with "secret not found":
```bash
# Check if secret exists
kubectl get secret cloudflare-access-credentials -n inference-benchmark

# Create it if missing
make create-secret CLIENT_ID=xxx CLIENT_SECRET=yyy
```

### Authentication Errors

If you get 403/401 errors:
1. Verify credentials are correct
2. Check Cloudflare Access policy allows the service token
3. Ensure the secret is in the correct namespace

### Check CronJob Logs

```bash
# List recent jobs
kubectl get jobs -n inference-benchmark

# View logs
kubectl logs -n inference-benchmark -l app=aiperf --tail=50
```

## Getting Cloudflare Access Credentials

If you don't have credentials yet:

1. **Go to**: https://one.dash.cloudflare.com/access/service-tokens
2. **Create** a new service token
3. **Copy** the Client ID and Client Secret
4. **Add** the token to your Access Application policy

Or use the setup script:
```bash
./scripts/setup-cloudflare-access.sh
```

## Image Registry

- **Registry**: GitHub Container Registry (ghcr.io)
- **Image**: `ghcr.io/hyperboliclabs/aiperf:latest`
- **Platform**: linux/amd64
