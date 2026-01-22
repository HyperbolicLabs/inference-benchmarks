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
    
    # Build command - use ddtrace-run with wrapper script for LLM Observability
    cmd = [
        "ddtrace-run", "python3", "run_with_ddtrace.py",
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
        # Run evaluation with real-time output and capture to check for "Total tasks: 0"
        import sys as sys_module
        captured_output = []
        zero_tasks_detected = False
        
        process = subprocess.Popen(
            cmd,
            cwd="/osworld",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream output in real-time and check for "Total tasks: 0"
        for line in process.stdout:
            line = line.rstrip()
            print(line)
            captured_output.append(line)
            if "Total tasks: 0" in line:
                zero_tasks_detected = True
        
        # Wait for process to complete
        returncode = process.wait()
        
        if returncode != 0:
            raise subprocess.CalledProcessError(returncode, cmd)
        
        # Check if 0 tasks were detected
        if zero_tasks_detected:
            # Check if this is because all tasks are already complete
            # OSWorld filters out tasks that already have result.txt files
            metrics = parse_osworld_results(result_dir)
            
            if metrics and metrics.get("total_tasks", 0) > 0:
                # Results exist - all tasks were already completed in previous runs
                print()
                print("=" * 60)
                print("✅ All tasks already completed")
                print("=" * 60)
                print(f"Found {metrics.get('total_tasks', 0)} completed tasks from previous runs")
                print(f"Success rate: {metrics.get('success_rate', 0):.1f}%")
                print("No new tasks to run - evaluation passed")
                
                # Send metrics to Datadog
                if metrics:
                    base_tags = [
                        f"model:{model_name}",
                        f"domain:{domain}",
                        "benchmark:osworld",
                        "cluster_name:inference-cluster"
                    ]
                    send_metrics_async(
                        metrics=metrics,
                        metric_prefix="inference.benchmark.osworld",
                        base_tags=base_tags
                    )
                
                sys.exit(0)
            else:
                # No results exist - this is a real failure (no tasks in test file)
                print()
                print("=" * 60)
                print("❌ Evaluation Failed: No tasks loaded from test file")
                print("=" * 60)
                print("OSWorld reported 'Total tasks: 0' and no previous results found")
                print("Possible causes:")
                print("  1. Test file is empty or missing")
                print("  2. Test file path is incorrect")
                print("  3. All tasks filtered out but no results exist (unexpected)")
                sys.exit(1)
        
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
        
        # Check if evaluation actually succeeded
        # OSWorld always exits with code 0, so we need to check the actual results
        # Pass criteria (based on OSWorld behavior):
        # 1. All tasks must complete (all tasks processed, queue empty)
        # 2. Not all tasks failed (at least some success - distinguishes from complete failure)
        evaluation_failed = False
        
        # Check: If metrics dict is empty or has no total_tasks, evaluation failed
        if not metrics:
            print("⚠️  No metrics found - evaluation may have failed")
            evaluation_failed = True
        elif "total_tasks" not in metrics:
            # No total_tasks in metrics means no result.txt files were found
            # This could mean 0 tasks were loaded OR all tasks failed before writing results
            # Check for partial results - if found, tasks were attempted but failed
            if "partial_results" in metrics:
                print(f"⚠️  Found {metrics['partial_results']} partial results but no completed tasks - evaluation failed")
            else:
                print("⚠️  No tasks completed and no partial results - evaluation failed (likely 0 tasks loaded)")
            evaluation_failed = True
        elif metrics.get("total_tasks", 0) == 0:
            print("⚠️  No tasks completed - evaluation failed")
            evaluation_failed = True
        elif metrics.get("success_rate", 0) == 0 and metrics.get("average_score", 0) == 0:
            # All tasks failed (100% failure rate) - this indicates a problem
            # Note: We don't require 100% success, but 0% success suggests a systemic issue
            print(f"⚠️  All {metrics.get('total_tasks', 0)} tasks failed (success_rate=0%, average_score=0) - evaluation failed")
            evaluation_failed = True
        else:
            # Evaluation passed: tasks completed and at least some succeeded
            success_rate = metrics.get("success_rate", 0)
            total_tasks = metrics.get("total_tasks", 0)
            successful_tasks = metrics.get("successful_tasks", 0)
            print(f"✅ Evaluation passed: {successful_tasks}/{total_tasks} tasks succeeded ({success_rate:.1f}% success rate)")
        
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
        
        # Exit with error code if evaluation failed
        if evaluation_failed:
            print()
            print("=" * 60)
            print("❌ Evaluation Failed: No successful tasks completed")
            print("=" * 60)
            sys.exit(1)
        
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
