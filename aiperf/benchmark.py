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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'common'))
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
    
    try:
        # Run AIPerf
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
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
        result_files = list(output_path.glob("*.json"))
        if result_files:
            results["result_files"] = [str(f) for f in result_files]
        
        return results
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Benchmark failed with exit code {e.returncode}")
        print(f"Error: {e.stderr}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": e.stderr,
            "exit_code": e.returncode,
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
    
    Args:
        result_dir: Directory containing JSON result files
    
    Returns:
        Dictionary of metric_name -> value
    """
    result_path = Path(result_dir)
    metrics = {}
    json_files = list(result_path.glob("*.json"))
    
    if not json_files:
        print(f"⚠️  No JSON result files found in {result_dir}")
        return metrics
    
    for json_file in json_files:
        try:
            with open(json_file) as f:
                data = json.load(f)
                
            if isinstance(data, dict):
                # Common AIPerf metrics - try multiple formats
                # Format 1: Nested structure
                if "latency" in data and isinstance(data["latency"], dict):
                    metrics["latency_p50"] = data["latency"].get("p50", 0)
                    metrics["latency_p95"] = data["latency"].get("p95", 0)
                    metrics["latency_p99"] = data["latency"].get("p99", 0)
                
                # Format 2: Direct keys
                for pct in ["50", "95", "99"]:
                    key = f"latency_p{pct}"
                    if key in data:
                        metrics[key] = data[key]
                
                if "throughput" in data and isinstance(data["throughput"], dict):
                    metrics["throughput_tokens_per_sec"] = data["throughput"].get("tokens_per_sec", 0)
                    metrics["throughput_requests_per_sec"] = data["throughput"].get("requests_per_sec", 0)
                
                # Direct throughput keys
                if "tokens_per_sec" in data:
                    metrics["throughput_tokens_per_sec"] = data["tokens_per_sec"]
                if "requests_per_sec" in data:
                    metrics["throughput_requests_per_sec"] = data["requests_per_sec"]
                
                # Time to first token
                for key in ["time_to_first_token", "ttft", "ttft_ms"]:
                    if key in data:
                        metrics["ttft_ms"] = data[key]
                        break
                
                # Inter token latency
                for key in ["inter_token_latency", "inter_token_latency_ms", "itl"]:
                    if key in data:
                        metrics["inter_token_latency_ms"] = data[key]
                        break
                
                # Direct metric extraction (fallback)
                for key in ["request_latency", "token_throughput", "request_throughput"]:
                    if key in data:
                        metrics[key] = data[key]
                        
        except json.JSONDecodeError as e:
            print(f"⚠️  Invalid JSON in {json_file}: {e}")
        except Exception as e:
            print(f"⚠️  Failed to parse {json_file}: {e}")
    
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
