"""
Railway entrypoint — run from backend/ as CWD.

Adds the repo root to sys.path so `backend` is a proper package,
then hands off to uvicorn. This keeps all relative imports working
without touching any existing source files.

  railway rootDirectory = "backend"
  startCommand = "python run.py"
"""
import os
import sys

# Repo root is one level up from this file (backend/run.py → /)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, log_level="info")
