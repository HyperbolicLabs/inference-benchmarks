#!/usr/bin/env python3
"""
OSWorld Evaluation Runner with Datadog Integration
Runs OSWorld evaluation and automatically sends results to Datadog
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add common directory to path
sys.path.insert(0, '/osworld/common')
from datadog_utils import send_metrics_async


def parse_osworld_results(result_dir: str) -> Dict[str, float]:
    """
    Parse OSWorld result files.
    
    Args:
        result_dir: Directory containing OSWorld results
    
    Returns:
        Dictionary of metric_name -> value
    """
    result_path = Path(result_dir)
    metrics = {}
    result_files = list(result_path.rglob("result.txt"))
    
    if not result_files:
        print(f"⚠️  No result.txt files found in {result_dir}")
        # Try to find partial results
        traj_files = list(result_path.rglob("traj.jsonl"))
        if traj_files:
            print(f"   Found {len(traj_files)} trajectory files (partial results)")
            metrics["partial_results"] = len(traj_files)
        return metrics
    
    total_tasks = 0
    successful_tasks = 0
    total_score = 0.0
    failed_parses = 0
    
    for result_file in result_files:
        try:
            with open(result_file) as f:
                content = f.read().strip()
                if not content:
                    print(f"⚠️  Empty result file: {result_file}")
                    failed_parses += 1
                    continue
                score = float(content)
                total_tasks += 1
                total_score += score
                if score > 0:
                    successful_tasks += 1
        except ValueError as e:
            print(f"⚠️  Invalid score in {result_file}: {e}")
            failed_parses += 1
        except Exception as e:
            print(f"⚠️  Failed to parse {result_file}: {e}")
            failed_parses += 1
    
    if total_tasks > 0:
        metrics["success_rate"] = (successful_tasks / total_tasks) * 100
        metrics["average_score"] = total_score / total_tasks
        metrics["total_tasks"] = total_tasks
        metrics["successful_tasks"] = successful_tasks
        metrics["failed_tasks"] = total_tasks - successful_tasks
        if failed_parses > 0:
            metrics["parse_errors"] = failed_parses
    
    return metrics


def main():
    """Main entry point - runs OSWorld evaluation and sends to Datadog."""
    # Get configuration from environment
    model_name = os.getenv("MODEL_NAME", "Qwen/Qwen3-VL-32B-Thinking")
    provider_name = os.getenv("PROVIDER_NAME", "docker")
    num_envs = os.getenv("NUM_ENVS", "1")
    max_steps = os.getenv("MAX_STEPS", "15")
    max_tokens = os.getenv("MAX_TOKENS", "32768")
    domain = os.getenv("DOMAIN", "all")
    test_meta_path = os.getenv("TEST_META_PATH", "evaluation_examples/test_nogdrive.json")
    result_dir = os.getenv("RESULT_DIR", "/osworld/results")
    action_space = os.getenv("ACTION_SPACE", "pyautogui")
    observation_type = os.getenv("OBSERVATION_TYPE", "screenshot")
    additional_args = os.getenv("ADDITIONAL_ARGS", "")
    
    # Create .env file for OSWorld
    openai_base_url = os.getenv("OPENAI_BASE_URL", "http://infra-inference-scheduling-inference-gateway.llm-d.svc.cluster.local/v1")
    openai_api_key = os.getenv("OPENAI_API_KEY", "dummy-key")
    
    env_file = Path("/osworld/.env")
    env_file.parent.mkdir(parents=True, exist_ok=True)
    with open(env_file, "w") as f:
        f.write(f"OPENAI_BASE_URL={openai_base_url}\n")
        f.write(f"OPENAI_API_KEY={openai_api_key}\n")
        f.write(f"OPENAI_MODEL={model_name}\n")
    
    print("=" * 60)
    print("OSWorld Evaluation")
    print("=" * 60)
    print(f"Model: {model_name}")
    print(f"Endpoint: {openai_base_url}")
    print(f"Provider: {provider_name}")
    print(f"Domain: {domain}")
    print(f"Result Dir: {result_dir}")
    print("=" * 60)
    print()
    
    # Build command
    cmd = [
        "python3", "run_multienv_qwen3vl.py",
        "--model", model_name,
        "--provider_name", provider_name,
        "--num_envs", num_envs,
        "--max_steps", max_steps,
        "--max_tokens", max_tokens,
        "--domain", domain,
        "--test_all_meta_path", test_meta_path,
        "--result_dir", result_dir,
        "--headless",
        "--action_space", action_space,
        "--observation_type", observation_type,
    ]
    
    if additional_args:
        # Split additional args and add to command
        import shlex
        cmd.extend(shlex.split(additional_args))
    
    # Run evaluation
    print("Running OSWorld evaluation...")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(
            cmd,
            cwd="/osworld",
            check=True
        )
        
        print()
        print("=" * 60)
        print("✅ Evaluation Complete")
        print("=" * 60)
        
        # Send to Datadog (async)
        print()
        print("=" * 60)
        print("Sending Results to Datadog")
        print("=" * 60)
        
        # Parse metrics
        metrics = parse_osworld_results(result_dir)
        
        if metrics:
            # Prepare tags
            base_tags = [
                f"model:{model_name}",
                f"domain:{domain}",
                "benchmark:osworld",
                "cluster_name:inference-cluster"
            ]
            
            # Send asynchronously
            send_metrics_async(
                metrics=metrics,
                metric_prefix="inference.benchmark.osworld",
                base_tags=base_tags
            )
        
        sys.exit(0)
        
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 60)
        print(f"❌ Evaluation Failed (exit code: {e.returncode})")
        print("=" * 60)
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print()
        print("Evaluation interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
