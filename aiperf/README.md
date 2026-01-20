# AIPerf Benchmark Script

This directory contains the AIPerf benchmarking setup for the inference endpoints.

## Overview

The benchmark script runs performance tests against the inference API endpoint using AIPerf. It supports:
- Cloudflare Access authentication
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

The CronJob requires Cloudflare Access credentials stored in a Kubernetes secret.

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

The CronJob reads credentials from a Kubernetes secret:

```yaml
env:
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

**Secret Structure:**
- Name: `cloudflare-access-credentials`
- Namespace: `inference-benchmark` (default)
- Keys:
  - `client-id`: Cloudflare Access Client ID
  - `client-secret`: Cloudflare Access Client Secret

### Locally (Testing)

Set environment variables:

```bash
export CF_ACCESS_CLIENT_ID="your-client-id"
export CF_ACCESS_CLIENT_SECRET="your-client-secret"
python3 benchmark.py
```

Or use a credentials file:

```bash
# Create cloudflare-access-credentials.txt
cat > cloudflare-access-credentials.txt <<EOF
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
EOF

# Source and run
source cloudflare-access-credentials.txt
python3 benchmark.py
```

## Configuration

### Environment Variables

The benchmark script supports these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `Qwen/Qwen3-VL-32B-Thinking` | Model identifier |
| `ENDPOINT_URL` | `https://inference.hyperbolic.ai` | API endpoint URL |
| `ENDPOINT_TYPE` | `chat` | Endpoint type (chat/completions/embeddings) |
| `CONCURRENCY` | `10` | Number of concurrent requests |
| `REQUEST_COUNT` | `100` | Total number of requests |
| `STREAMING` | `true` | Enable streaming responses |
| `OUTPUT_DIR` | `/tmp/aiperf-results` | Results directory |
| `CF_ACCESS_CLIENT_ID` | - | Cloudflare Access Client ID (optional) |
| `CF_ACCESS_CLIENT_SECRET` | - | Cloudflare Access Client Secret (optional) |
| `REQUEST_TIMEOUT` | - | Request timeout in seconds (optional) |
| `OUTPUT_TOKENS_MEAN` | - | Mean output tokens per response (optional) |
| `BENCHMARK_DURATION` | - | Benchmark duration in seconds (optional) |
| `BENCHMARK_GRACE_PERIOD` | - | Grace period after benchmark ends (optional) |

### CronJob Configuration

The CronJob is configured with:
- **Schedule**: Every 10 minutes (`*/10 * * * *`)
- **Duration**: 8 minutes per benchmark
- **Concurrency**: 20 requests
- **Timeout**: 60 seconds per request
- **Output Tokens**: Mean of 50 tokens per response

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
