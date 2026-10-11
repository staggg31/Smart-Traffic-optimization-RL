"""Standalone runner for the Traffic-Opt-RL FastAPI backend service.

Can be safely executed from any directory (project root, frontend, etc.).
"""

import os
import sys

# Compute project root from script location
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if __name__ == "__main__":
    import uvicorn
    print(f"Starting Traffic-Opt-RL backend from root: {PROJECT_ROOT}")
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True, app_dir=PROJECT_ROOT)
