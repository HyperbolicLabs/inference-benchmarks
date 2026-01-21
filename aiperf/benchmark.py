#!/usr/bin/env python3
"""
AIPerf Benchmark Script for Inference Endpoints
Runs performance benchmarks against inference endpoints using AIPerf
"""

import os
import sys
import subprocess
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Add common directory to path
sys.path.insert(0, '/scripts/common')
from datadog_utils import send_metrics_async


def run_benchmark(
    model_name: str,
    endpoint_url: str,
    endpoint_type: str = "chat",
    concurrency: int = 20,
    request_count: int = 100,
    streaming: bool = True,
    output_dir: str = "/tmp/aiperf-results",
    benchmark_duration: Optional[int] = None,
    benchmark_grace_period: Optional[int] = None,
    request_timeout_seconds: Optional[float] = None,
    output_tokens_mean: Optional[int] = None,
    cf_access_client_id: Optional[str] = None,
    cf_access_client_secret: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Run AIPerf benchmark against an inference endpoint.
    
    Args:
        model_name: Model identifier (e.g., "Qwen/Qwen3-VL-32B-Thinking")
        endpoint_url: Inference endpoint URL
        endpoint_type: Type of endpoint (chat, completions, embeddings)
        concurrency: Number of concurrent requests
        request_count: Total number of requests
        streaming: Enable streaming
        output_dir: Directory for results
        output_tokens_mean: Mean number of output tokens per response
        cf_access_client_id: Cloudflare Access Client ID (optional)
        cf_access_client_secret: Cloudflare Access Client Secret (optional)
        **kwargs: Additional AIPerf arguments
    
    Returns:
        Dictionary with benchmark results and metadata
    """
    print("=" * 60)
    print("AIPerf Benchmark")
    print("=" * 60)
    print(f"Model: {model_name}")
    print(f"Endpoint: {endpoint_url}")
    print(f"Type: {endpoint_type}")
    print(f"Concurrency: {concurrency}")
    if benchmark_duration:
        print(f"Duration: {benchmark_duration}s")
        if benchmark_grace_period:
            print(f"Grace Period: {benchmark_grace_period}s")
    else:
        print(f"Request Count: {request_count}")
    if output_tokens_mean:
        print(f"Output Tokens Mean: {output_tokens_mean}")
    print(f"Streaming: {streaming}")
    print(f"Output Directory: {output_dir}")
    if cf_access_client_id:
        print(f"Cloudflare Access: Enabled (Client ID: {cf_access_client_id[:20]}...)")
    print("=" * 60)
    print()
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Build AIPerf command
    cmd = [
        "aiperf", "profile",
        "--model", model_name,
        "--url", endpoint_url,
        "--endpoint-type", endpoint_type,
        "--concurrency", str(concurrency),
        "--output-artifact-dir", output_dir,
        "--ui-type", "none",  # Disable TUI for non-interactive environments (Kubernetes/containers)
        "--no-server-metrics",  # Disable server metrics to avoid timeout on unreachable Prometheus endpoints (known issue in v0.4.0+)
    ]
    
    # AIPerf doesn't allow both --request-count and --benchmark-duration together
    if benchmark_duration is not None:
        cmd.extend(["--benchmark-duration", str(benchmark_duration)])
        if benchmark_grace_period is not None:
            cmd.extend(["--benchmark-grace-period", str(benchmark_grace_period)])
    else:
        cmd.extend(["--request-count", str(request_count)])
    
    if streaming:
        cmd.append("--streaming")
    
    if request_timeout_seconds is not None:
        cmd.extend(["--request-timeout-seconds", str(request_timeout_seconds)])
    
    if output_tokens_mean is not None:
        cmd.extend(["--output-tokens-mean", str(output_tokens_mean)])
    
    # Add Cloudflare Access headers if provided
    if cf_access_client_id and cf_access_client_secret:
        cmd.extend(["--header", f"CF-Access-Client-Id: {cf_access_client_id}"])
        cmd.extend(["--header", f"CF-Access-Client-Secret: {cf_access_client_secret}"])
    
    # Add any additional kwargs
    for key, value in kwargs.items():
        if value is not None:
            flag_name = key.replace('_', '-')
            cmd.extend([f"--{flag_name}", str(value)])
    
    print(f"Running command: {' '.join(cmd)}")
    print()
    
    # Prepare environment variables to disable TUI in non-interactive environments
    env = os.environ.copy()
    env['TERM'] = 'dumb'  # Disable terminal capabilities
    env['CI'] = 'true'    # Signal CI/non-interactive environment
    env['NO_COLOR'] = '1'  # Disable ANSI color codes
    env['PYTHONUNBUFFERED'] = '1'  # Disable Python output buffering
    
    # Set AIPerf timeout environment variables to prevent timeout errors
    # These timeouts control how long AIPerf waits for services to respond during startup
    # Increase them for slower environments (e.g., Kubernetes with resource constraints)
    env.setdefault('AIPERF_SERVICE_PROFILE_CONFIGURE_TIMEOUT', '600.0')  # 10 minutes for configuration
    env.setdefault('AIPERF_SERVICE_PROFILE_START_TIMEOUT', '300.0')  # 5 minutes for start profiling
    env.setdefault('AIPERF_DATASET_CONFIGURATION_TIMEOUT', '600.0')  # 10 minutes for dataset config
    
    try:
        # Run AIPerf with --ui-type none to disable TUI completely
        # This is the proper way to run AIPerf in non-interactive environments (Kubernetes/containers)
        # With --ui-type none, AIPerf should exit cleanly without TUI-related errors
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,  # Redirect stdin to prevent any TUI detection
            stdout=subprocess.PIPE,    # Use PIPE (not TTY) - makes isatty() return False
            stderr=subprocess.STDOUT,  # Merge stderr into stdout to capture all output
            text=True,
            check=True,  # With --ui-type none, AIPerf should exit cleanly
            env=env,  # Pass environment with TUI-disabling variables
            timeout=None  # No timeout - let benchmark run for full duration
        )
        
        print("✅ Benchmark completed successfully")
        print(f"Results saved to: {output_dir}")
        
        # Parse results if available
        results = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "model": model_name,
            "endpoint": endpoint_url,
            "output_dir": output_dir,
            "stdout": result.stdout,
        }
        
        # Try to find and parse result files
        result_files = list(output_path.glob("*.json*"))
        if result_files:
            results["result_files"] = [str(f) for f in result_files]
        
        return results
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Benchmark failed with exit code {e.returncode}")
        
        # Check if result files exist despite the error (partial success)
        result_files = list(output_path.glob("*.json*"))
        if result_files:
            print(f"⚠️  Warning: Exit code {e.returncode}, but result files found:")
            for f in result_files:
                print(f"   - {f}")
            print("   This may indicate a non-fatal error (e.g., timeout during cleanup)")
        
        # Show error output (truncated for readability)
        stdout_preview = e.stdout[:1000] if e.stdout else '(empty)'
        stderr_preview = e.stderr[:1000] if e.stderr else '(empty)'
        print(f"\nStdout preview (first 1000 chars):\n{stdout_preview}")
        if e.stderr and e.stderr != e.stdout:
            print(f"\nStderr preview (first 1000 chars):\n{stderr_preview}")
        
        # Check for common error patterns
        error_msg = e.stderr or e.stdout or "Unknown error"
        if "TimeoutError" in error_msg or "timeout" in error_msg.lower():
            print("\n💡 Tip: If you see timeout errors, try increasing:")
            print("   - AIPERF_SERVICE_PROFILE_START_TIMEOUT")
            print("   - AIPERF_SERVICE_PROFILE_CONFIGURE_TIMEOUT")
            print("   - AIPERF_DATASET_CONFIGURATION_TIMEOUT")
        
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_msg,
            "exit_code": e.returncode,
            "stdout": e.stdout,
            "stderr": e.stderr,
            "result_files": [str(f) for f in result_files] if result_files else None,
        }
    except FileNotFoundError:
        print("❌ AIPerf not found. Please install it with: pip install aiperf")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": "AIPerf not installed",
        }


def parse_aiperf_results(result_dir: str) -> Dict[str, float]:
    """
    Parse AIPerf JSON result files.
    
    AIPerf exports metrics in profile_export_aiperf.json with structure:
    {
        "metrics": {
            "metric_name": {
                "stats": {
                    "mean": ...,
                    "p50": ...,
                    "p95": ...,
                    "p99": ...,
                    ...
                }
            }
        }
    }
    
    Args:
        result_dir: Directory containing JSON result files
    
    Returns:
        Dictionary of metric_name -> value
    """
    result_path = Path(result_dir)
    metrics = {}
    
    # Look specifically for profile_export_aiperf.json (the aggregated stats file)
    json_file = result_path / "profile_export_aiperf.json"
    
    if not json_file.exists():
        # Fallback: try any JSON file
        json_files = list(result_path.glob("*.json"))
        if not json_files:
            print(f"⚠️  No JSON result files found in {result_dir}")
            return metrics
        json_file = json_files[0]
    
    try:
        with open(json_file) as f:
            data = json.load(f)
        
        if not isinstance(data, dict):
            print(f"⚠️  Expected dict in {json_file}, got {type(data)}")
            return metrics
        
        # AIPerf structure: data[metric_name] = JsonMetricResult with stats directly inside
        # Example: data["request_latency"] = {"unit": "ms", "avg": 123.4, "p50": 100.0, "p95": 200.0, "p99": 300.0, ...}
        # Common metric field names in JsonExportData
        metric_fields = [
            "request_latency", "time_to_first_token", "time_to_second_token",
            "inter_token_latency", "inter_chunk_latency",
            "request_throughput", "output_token_throughput", "output_token_throughput_per_user",
            "request_count", "good_request_count", "error_request_count",
            "output_sequence_length", "input_sequence_length",
            "output_token_count", "reasoning_token_count",
            "goodput", "total_output_tokens", "total_reasoning_tokens",
            "benchmark_duration", "total_isl", "total_osl", "error_isl", "total_error_isl"
        ]
        
        for metric_field in metric_fields:
            if metric_field in data:
                metric_data = data[metric_field]
                # Skip if None (JsonExportData fields can be None)
                if metric_data is None:
                    continue
                # Must be a dict (JsonMetricResult)
                if not isinstance(metric_data, dict):
                    continue
                
                # Extract stats from JsonMetricResult structure
                # JsonMetricResult has: unit, avg, p50, p95, p99, min, max, std, etc.
                for stat in ["avg", "p50", "p95", "p99", "min", "max", "std"]:
                    if stat in metric_data and metric_data[stat] is not None:
                        try:
                            metrics[f"{metric_field}_{stat}"] = float(metric_data[stat])
                        except (ValueError, TypeError):
                            pass
        
        # Also check for nested metrics structure (alternative format)
        if "metrics" in data and isinstance(data["metrics"], dict):
            for metric_name, metric_data in data["metrics"].items():
                if isinstance(metric_data, dict):
                    # Check if stats are nested or direct
                    if "stats" in metric_data and isinstance(metric_data["stats"], dict):
                        stats = metric_data["stats"]
                        if "mean" in stats:
                            metrics[f"{metric_name}_mean"] = float(stats["mean"])
                        if "p50" in stats:
                            metrics[f"{metric_name}_p50"] = float(stats["p50"])
                        if "p95" in stats:
                            metrics[f"{metric_name}_p95"] = float(stats["p95"])
                        if "p99" in stats:
                            metrics[f"{metric_name}_p99"] = float(stats["p99"])
                    else:
                        # Stats are directly in metric_data
                        for stat in ["avg", "mean", "p50", "p95", "p99", "min", "max", "std"]:
                            if stat in metric_data:
                                try:
                                    metrics[f"{metric_name}_{stat}"] = float(metric_data[stat])
                                except (ValueError, TypeError):
                                    pass
        
        # Also check for direct metric keys (legacy format support)
        for key in ["latency_p50", "latency_p95", "latency_p99", "ttft", "ttft_ms", 
                    "tokens_per_sec", "requests_per_sec", "throughput_tokens_per_sec", 
                    "throughput_requests_per_sec"]:
            if key in data:
                try:
                    metrics[key] = float(data[key])
                except (ValueError, TypeError):
                    pass
        
        # Check nested structures (legacy format)
        if "latency" in data and isinstance(data["latency"], dict):
            for pct in ["50", "95", "99"]:
                key = f"latency_p{pct}"
                if key in data["latency"]:
                    try:
                        metrics[key] = float(data["latency"][key])
                    except (ValueError, TypeError):
                        pass
        
        if "throughput" in data and isinstance(data["throughput"], dict):
            if "tokens_per_sec" in data["throughput"]:
                try:
                    metrics["throughput_tokens_per_sec"] = float(data["throughput"]["tokens_per_sec"])
                except (ValueError, TypeError):
                    pass
            if "requests_per_sec" in data["throughput"]:
                try:
                    metrics["throughput_requests_per_sec"] = float(data["throughput"]["requests_per_sec"])
                except (ValueError, TypeError):
                    pass
                    
    except json.JSONDecodeError as e:
        print(f"⚠️  Invalid JSON in {json_file}: {e}")
    except Exception as e:
        print(f"⚠️  Failed to parse {json_file}: {e}")
        import traceback
        traceback.print_exc()
    
    if metrics:
        print(f"✅ Parsed {len(metrics)} metrics from {json_file.name}")
    else:
        print(f"⚠️  No metrics extracted from {json_file.name}")
        # Debug: print structure
        try:
            with open(json_file) as f:
                data = json.load(f)
                print(f"   File structure keys: {list(data.keys())[:10]}")
        except:
            pass
    
    return metrics


def main():
    """Main entry point for the benchmark script."""
    # Get configuration from environment variables or use defaults
    model_name = os.getenv("MODEL_NAME", "Qwen/Qwen3-VL-32B-Thinking")
    endpoint_url = os.getenv("ENDPOINT_URL", "https://inference.hyperbolic.ai")
    endpoint_type = os.getenv("ENDPOINT_TYPE", "chat")
    concurrency = int(os.getenv("CONCURRENCY", "10"))
    request_count = int(os.getenv("REQUEST_COUNT", "100"))
    streaming = os.getenv("STREAMING", "true").lower() == "true"
    output_dir = os.getenv("OUTPUT_DIR", "/tmp/aiperf-results")
    
    # Cloudflare Access credentials (optional)
    cf_access_client_id = os.getenv("CF_ACCESS_CLIENT_ID")
    cf_access_client_secret = os.getenv("CF_ACCESS_CLIENT_SECRET")
    
    # Additional optional parameters
    timeout = os.getenv("REQUEST_TIMEOUT")
    output_tokens_mean = os.getenv("OUTPUT_TOKENS_MEAN")
    benchmark_duration = os.getenv("BENCHMARK_DURATION")
    benchmark_grace_period = os.getenv("BENCHMARK_GRACE_PERIOD")
    
    kwargs = {}
    if timeout:
        kwargs["request_timeout_seconds"] = float(timeout)
    if output_tokens_mean:
        kwargs["output_tokens_mean"] = int(output_tokens_mean)
    if benchmark_duration:
        kwargs["benchmark_duration"] = float(benchmark_duration)
    if benchmark_grace_period:
        kwargs["benchmark_grace_period"] = float(benchmark_grace_period)
    
    # Run benchmark
    results = run_benchmark(
        model_name=model_name,
        endpoint_url=endpoint_url,
        endpoint_type=endpoint_type,
        concurrency=concurrency,
        request_count=request_count,
        streaming=streaming,
        output_dir=output_dir,
        cf_access_client_id=cf_access_client_id,
        cf_access_client_secret=cf_access_client_secret,
        **kwargs
    )
    
    # Print results summary
    print()
    print("=" * 60)
    print("Benchmark Summary")
    print("=" * 60)
    print(json.dumps(results, indent=2))
    
    # Send to Datadog if benchmark was successful (async)
    if results.get("status") == "success":
        print()
        print("=" * 60)
        print("Sending Results to Datadog")
        print("=" * 60)
        
        # Parse metrics
        metrics = parse_aiperf_results(output_dir)
        
        if metrics:
            # Prepare tags
            base_tags = [
                f"model:{model_name}",
                f"endpoint:{endpoint_url}",
                "benchmark:aiperf",
                "cluster_name:inference-cluster"
            ]
            
            # Send asynchronously
            send_metrics_async(
                metrics=metrics,
                metric_prefix="inference.benchmark.aiperf",
                base_tags=base_tags
            )
    
    # Exit with appropriate code
    sys.exit(0 if results.get("status") == "success" else 1)


if __name__ == "__main__":
    main()
