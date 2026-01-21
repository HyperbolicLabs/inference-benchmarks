#!/usr/bin/env python3
"""
Wrapper script to enable ddtrace instrumentation for OSWorld.
Monkey-patches Qwen3VLAgent to use OpenAI backend (required for ddtrace).
"""
import sys
import os

# Add OSWorld to path
sys.path.insert(0, '/osworld')

# Monkey-patch Qwen3VLAgent BEFORE it's imported by run_multienv_qwen3vl
from mm_agents.qwen3vl_agent import Qwen3VLAgent

# Save original __init__
_original_init = Qwen3VLAgent.__init__

def patched_init(self, *args, **kwargs):
    """Force api_backend to 'openai' if not specified (required for ddtrace)."""
    if 'api_backend' not in kwargs:
        kwargs['api_backend'] = 'openai'
    return _original_init(self, *args, **kwargs)

# Apply monkey-patch
Qwen3VLAgent.__init__ = patched_init

# Now execute the original script
# The wrapper is called with arguments that should be passed to run_multienv_qwen3vl.py
if __name__ == "__main__":
    # The arguments passed to this script should be passed to run_multienv_qwen3vl.py
    # sys.argv[0] is the script name, rest are arguments
    original_script = '/osworld/run_multienv_qwen3vl.py'
    
    # Read and execute the original script
    with open(original_script, 'r') as f:
        script_code = f.read()
    
    # Update sys.argv to match what the original script expects
    # Keep sys.argv[0] as the original script path, pass through all arguments
    sys.argv = [original_script] + sys.argv[1:]
    
    # Execute the script in the current namespace (so monkey-patch is active)
    exec(compile(script_code, original_script, 'exec'), {
        '__name__': '__main__',
        '__file__': original_script,
        '__package__': None,
    })
