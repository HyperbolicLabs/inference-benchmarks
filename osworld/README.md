# OSWorld Evaluation

This directory contains tools for running full OSWorld evaluations against your inference endpoint.

## Overview

OSWorld is a benchmark for evaluating agents in desktop environments. This setup allows you to:
- Run OSWorld evaluations using your inference endpoint
- Test Qwen3VL agent performance on desktop automation tasks
- Run evaluations in Kubernetes with desktop environment support

## Files

- `Dockerfile` - Container with OSWorld and dependencies
- `osworld-job.yaml` - Kubernetes Job for running evaluations
- `Makefile` - Build and deployment automation

## Quick Start

### 1. Build and Push Image

```bash
cd scripts/osworld

# Build the image (includes OSWorld repository)
make build

# Push to registry (requires GITHUB_TOKEN)
export GITHUB_TOKEN=your_token
make push

# Or do both at once
make build-push
```

### 2. Configure Evaluation

Edit `osworld-job.yaml` to customize:
- Number of parallel environments (`NUM_ENVS`)
- Maximum steps per task (`MAX_STEPS`)
- Domain to test (`DOMAIN`)
- Test configuration file (`TEST_META_PATH`)

### 3. Deploy and Run

```bash
# Deploy evaluation job
make deploy

# Monitor progress
make logs

# Check status
make status
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_BASE_URL` | Internal gateway URL | Inference endpoint |
| `OPENAI_API_KEY` | `dummy-key` | API key (usually not needed) |
| `MODEL_NAME` | `Qwen/Qwen3-VL-32B-Thinking` | Model identifier |
| `PROVIDER_NAME` | `docker` | Desktop environment provider |
| `NUM_ENVS` | `1` | Parallel environments |
| `MAX_STEPS` | `15` | Max steps per task |
| `MAX_TOKENS` | `32768` | Max tokens per request |
| `DOMAIN` | `all` | Domain to test |
| `TEST_META_PATH` | `evaluation_examples/test_nogdrive.json` | Test config |
| `RESULT_DIR` | `/osworld/results` | Results directory |
| `ACTION_SPACE` | `pyautogui` | Action space type |
| `OBSERVATION_TYPE` | `screenshot` | Observation type |

### Customizing Evaluation

#### Run Specific Domain
```yaml
env:
- name: DOMAIN
  value: "web"  # Instead of "all"
```

#### Increase Parallelism
```yaml
env:
- name: NUM_ENVS
  value: "2"  # Run 2 environments in parallel
```

#### Use Different Test Set
```yaml
env:
- name: TEST_META_PATH
  value: "evaluation_examples/custom_tests.json"
```

#### Additional Arguments
```yaml
env:
- name: ADDITIONAL_ARGS
  value: "--temperature 0.7 --top_p 0.95"
```

## How It Works

1. **Container Setup**: 
   - Clones OSWorld repository
   - Installs all dependencies
   - Sets up desktop environment support
   - **Note**: VM image (~11.4GB) is NOT included in Docker image
   - OSWorld automatically downloads VM image on first run if not cached

2. **Endpoint Configuration**:
   - Creates `.env` file with endpoint settings
   - OSWorld's `Qwen3VLAgent` reads from environment variables

3. **VM Image Caching**:
   - VM image is cached in PVC (`osworld-vm-cache`)
   - First run downloads VM image (adds 3-4 minutes)
   - Subsequent runs reuse cached VM image (instant)

4. **Evaluation Execution**:
   - Runs `run_multienv_qwen3vl.py` with configured parameters
   - Creates desktop environments (Docker containers)
   - Runs agent tasks in parallel
   - Collects results

5. **Results**:
   - Stored in `/osworld/results` (PVC)
   - Includes trajectories, screenshots, recordings
   - Results persist until job TTL expires (24 hours)

## Results Access

### View Logs
```bash
make logs
# Or directly:
kubectl logs -l app=osworld,component=evaluation -n inference-benchmark -f
```

### Access Results (if using PVC)
If you modify the job to use a PersistentVolumeClaim, results will persist:
```yaml
volumes:
- name: results
  persistentVolumeClaim:
    claimName: osworld-results
```

### Download Results
```bash
# Copy results from pod
kubectl cp inference-benchmark/<pod-name>:/osworld/results ./local-results
```

## Troubleshooting

### Privileged Mode Issues
If your cluster doesn't allow privileged containers:
- Use a different provider (e.g., `aws` instead of `docker`)
- Request cluster admin to enable privileged mode for your namespace
- Use a dedicated node pool with privileged access

### Docker Socket Access
If Docker socket is not accessible:
- Ensure nodes have Docker installed
- Check volume mount permissions
- Consider using containerd socket instead

### Resource Constraints
If job is OOMKilled:
- Increase memory limits in `osworld-job.yaml`
- Reduce `NUM_ENVS` (fewer parallel environments)
- Use nodes with more resources

### Long Running Evaluations
OSWorld evaluations can take hours:
- Set appropriate `ttlSecondsAfterFinished` (default: 24 hours)
- Consider using a CronJob for periodic evaluations
- Monitor resource usage during long runs

## References

- [OSWorld Repository](https://github.com/xlang-ai/OSWorld)
- [run_multienv_qwen3vl.py](https://github.com/xlang-ai/OSWorld/blob/main/run_multienv_qwen3vl.py)
- [Qwen3VLAgent Documentation](https://github.com/xlang-ai/OSWorld/tree/main/mm_agents)
