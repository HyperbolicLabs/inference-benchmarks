#!/usr/bin/env python3
"""
Common Datadog utilities for benchmark metrics export
Shared by AIPerf and OSWorld benchmarks

- AIPerf: Uses Custom Metrics API (aggregated benchmark results)
- OSWorld: Uses Custom Metrics API (aggregated task results)
  Note: OSWorld can also use LLM Observability via ddtrace for individual LLM call tracing
"""

import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional


def initialize_datadog() -> bool:
    """
    Initialize Datadog client.
    
    Returns:
        True if initialized successfully, False otherwise
    """
    try:
        from datadog import initialize, api
    except ImportError:
        print("⚠️  Datadog package not installed, skipping Datadog export")
        return False
    
    api_key = os.getenv("DD_API_KEY")
    if not api_key:
        print("⚠️  DD_API_KEY not set, skipping Datadog export")
        return False
    
    app_key = os.getenv("DD_APP_KEY")
    if app_key:
        initialize(api_key=api_key, app_key=app_key)
    else:
        initialize(api_key=api_key)
    
    return True


def send_metrics_to_datadog(
    metrics: Dict[str, float],
    metric_prefix: str,
    base_tags: List[str],
    max_retries: int = 3,
    batch_size: int = 20
) -> bool:
    """
    Send metrics to Datadog with retry logic and batching.
    
    Args:
        metrics: Dictionary of metric_name -> value
        metric_prefix: Prefix for metric names (e.g., "inference.benchmark.aiperf")
        base_tags: Base tags for all metrics
        max_retries: Maximum number of retry attempts
        batch_size: Number of metrics per batch
    
    Returns:
        True if successful (including partial success)
    """
    if not initialize_datadog():
        return False
    
    from datadog import api
    
    # Prepare metrics for Datadog
    datadog_metrics = []
    for metric_name, value in metrics.items():
        if value is not None and isinstance(value, (int, float)):
            datadog_metrics.append({
                "metric": f"{metric_prefix}.{metric_name}",
                "points": [(int(datetime.now().timestamp()), value)],
                "tags": base_tags,
                "type": "gauge"
            })
    
    if not datadog_metrics:
        print("⚠️  No metrics to send to Datadog")
        return False
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            # Send in batches for better reliability
            success_count = 0
            total_batches = (len(datadog_metrics) + batch_size - 1) // batch_size
            
            for i in range(0, len(datadog_metrics), batch_size):
                batch = datadog_metrics[i:i+batch_size]
                batch_num = i // batch_size + 1
                
                try:
                    response = api.Metric.send(batch)
                    if response.get("status") == "ok":
                        success_count += len(batch)
                    else:
                        print(f"⚠️  Batch {batch_num}/{total_batches} failed: {response}")
                except Exception as e:
                    print(f"⚠️  Batch {batch_num}/{total_batches} exception: {e}")
            
            if success_count == len(datadog_metrics):
                print(f"✅ Sent {len(datadog_metrics)} metrics to Datadog")
                return True
            elif success_count > 0:
                print(f"⚠️  Partially sent {success_count}/{len(datadog_metrics)} metrics to Datadog")
                return True  # Partial success is acceptable
            else:
                raise Exception("All batches failed")
                
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"⚠️  Datadog send failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                print(f"❌ Failed to send metrics to Datadog after {max_retries} attempts: {e}")
                return False
    
    return False


def send_metrics_async(
    metrics: Dict[str, float],
    metric_prefix: str,
    base_tags: List[str],
    max_retries: int = 3,
    batch_size: int = 20
) -> None:
    """
    Send metrics to Datadog asynchronously (non-blocking).
    
    Uses Datadog Custom Metrics API for benchmark results.
    
    Args:
        metrics: Dictionary of metric_name -> value
        metric_prefix: Prefix for metric names (e.g., "inference.benchmark.aiperf")
        base_tags: Base tags for all metrics
        max_retries: Maximum number of retry attempts
        batch_size: Number of metrics per batch
    """
    import threading
    
    def _send():
        send_metrics_to_datadog(
            metrics=metrics,
            metric_prefix=metric_prefix,
            base_tags=base_tags,
            max_retries=max_retries,
            batch_size=batch_size
        )
    
    # Use non-daemon thread so it completes before pod exits
    # This ensures metrics are sent and we see success/failure messages in logs
    thread = threading.Thread(target=_send, daemon=False)
    thread.start()
    # Wait for thread to complete (with timeout to prevent hanging)
    thread.join(timeout=30)  # Wait up to 30 seconds for metrics to be sent
    if thread.is_alive():
        print("⚠️  Metrics sending thread still running after 30s timeout, continuing...")


def send_metrics_to_llm_observability(
    metrics: Dict[str, float],
    base_tags: List[str],
    max_retries: int = 3
) -> bool:
    """
    Send benchmark metrics to Datadog LLM Observability.
    
    Uses LLM Observability's evaluation/experiment tracking to record benchmark results.
    Maps AIPerf metrics to standard LLM Observability metric names where applicable.
    
    Args:
        metrics: Dictionary of metric_name -> value
        base_tags: Base tags for all metrics
        max_retries: Maximum number of retry attempts
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from ddtrace import tracer
        from ddtrace.llmobs import LLMObs
    except ImportError:
        print("⚠️  ddtrace package not installed, skipping LLM Observability export")
        print("   Install with: pip install ddtrace")
        return False
    
    # Check if LLM Observability is enabled
    if not os.getenv("DD_LLMOBS_ENABLED"):
        print("⚠️  DD_LLMOBS_ENABLED not set, skipping LLM Observability export")
        return False
    
    # Note: With agent mode, DD_API_KEY is not required in the pod
    # The agent handles authentication. Only needed for agentless mode.
    # Check if we're in agentless mode
    agentless = os.getenv("DD_LLMOBS_AGENTLESS_ENABLED") == "1"
    if agentless:
        api_key = os.getenv("DD_API_KEY")
        if not api_key:
            print("⚠️  DD_API_KEY not set (required for agentless mode), skipping LLM Observability export")
            return False
    
    # Extract model and endpoint from tags
    model_name = None
    endpoint_url = None
    ml_app = os.getenv("DD_LLMOBS_ML_APP", "aiperf-benchmark")
    
    for tag in base_tags:
        if tag.startswith("model:"):
            model_name = tag.split(":", 1)[1]
        elif tag.startswith("endpoint:"):
            endpoint_url = tag.split(":", 1)[1]
    
    # Map AIPerf metrics to standard LLM Observability metric names
    # Only map to metrics that actually exist in Datadog LLM Observability
    # Reference: https://docs.datadoghq.com/llm_observability/monitoring/metrics/
    standard_metric_mapping = {
        # Duration/Latency - map to span duration (in seconds, not ms)
        "request_latency_avg": "ml_obs.span.duration",  # Convert ms to seconds when setting
        
        # Token metrics - standard LLM Observability metrics
        "input_sequence_length_avg": "ml_obs.span.llm.input.tokens",
        "output_sequence_length_avg": "ml_obs.span.llm.output.tokens",
        "output_token_count_avg": "ml_obs.span.llm.output.tokens",  # Alternative name
        "total_output_tokens_avg": "ml_obs.span.llm.total.tokens",
        "reasoning_token_count_avg": "ml_obs.span.llm.output.reasoning.tokens",
        
        # Error metrics
        "error_request_count_avg": "ml_obs.span.error",
    }
    
    # Metrics that need unit conversion (ms to seconds)
    metrics_requiring_conversion = {
        "request_latency_avg": 0.001,  # Convert ms to seconds
    }
    
    # Create a span for the benchmark run
    with tracer.trace("llm.benchmark", service="aiperf-benchmark") as span:
        # Set standard LLM Observability tags (required for proper integration)
        span.set_tag("ml_app", ml_app)
        span.set_tag("span_kind", "workflow")  # Benchmark is a workflow, not individual LLM call
        span.set_tag("model_name", model_name or "unknown")
        span.set_tag("model_provider", "custom")  # Custom endpoint, not standard provider
        span.set_tag("benchmark.type", "aiperf")
        span.set_tag("endpoint.url", endpoint_url or "unknown")
        
        # Add all base tags
        for tag in base_tags:
            if ":" in tag:
                key, value = tag.split(":", 1)
                # Use standard tag names where applicable
                if key == "model":
                    span.set_tag("model_name", value)
                elif key == "cluster_name":
                    span.set_tag("env", value)
                else:
                    span.set_tag(key, value)
        
        # Add standard LLM Observability metrics where we have mappings
        standard_metrics = {}
        custom_metrics = {}
        
        for metric_name, value in metrics.items():
            if value is not None and isinstance(value, (int, float)):
                # Check if we have a standard mapping
                if metric_name in standard_metric_mapping:
                    std_name = standard_metric_mapping[metric_name]
                    
                    # Apply unit conversion if needed (e.g., ms to seconds)
                    converted_value = value
                    if metric_name in metrics_requiring_conversion:
                        converted_value = value * metrics_requiring_conversion[metric_name]
                    
                    if std_name not in standard_metrics:
                        standard_metrics[std_name] = []
                    standard_metrics[std_name].append(converted_value)
                else:
                    # Keep custom metrics for output_data
                    # This includes: latency percentiles, throughput, time_to_first_token, etc.
                    custom_metrics[metric_name] = value
        
        # Set standard metrics on span (use average if multiple values map to same metric)
        for std_name, values in standard_metrics.items():
            avg_value = sum(values) / len(values) if values else 0
            span.set_metric(std_name, avg_value)
        
        # Use LLM Observability to annotate the span with benchmark results
        try:
            LLMObs.annotate(
                span=span,
                input_data={
                    "benchmark_type": "aiperf",
                    "model": model_name,
                    "endpoint": endpoint_url,
                },
                output_data={
                    "benchmark_metrics": custom_metrics,  # Custom metrics in output_data
                    "standard_metrics": {k: sum(v)/len(v) for k, v in standard_metrics.items()},
                    "metric_count": len(metrics),
                },
                tags=base_tags,
            )
            print(f"✅ Sent {len(metrics)} benchmark metrics to Datadog LLM Observability")
            print(f"   Standard metrics: {len(standard_metrics)}, Custom metrics: {len(custom_metrics)}")
            return True
        except Exception as e:
            print(f"⚠️  Failed to annotate span with LLM Observability: {e}")
            import traceback
            traceback.print_exc()
            # Still return True since span was created with metrics
            return True
    
    return False
