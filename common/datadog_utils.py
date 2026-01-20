#!/usr/bin/env python3
"""
Common Datadog utilities for benchmark metrics export
Shared by AIPerf and OSWorld benchmarks
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
    
    Args:
        metrics: Dictionary of metric_name -> value
        metric_prefix: Prefix for metric names
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
    
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
    # Give it a moment to start
    time.sleep(0.5)
