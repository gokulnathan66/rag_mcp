# RAG MCP Server (scaffold)

This folder holds a minimal scaffold for the RAG MCP Server described in the project design.

Quick start (local):

1. Create a virtual environment and install requirements:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the app:

```bash
uvicorn app.main:app --reload
```

3. Health check:

```bash
curl http://localhost:8000/health
```

Notes:
- This is a scaffold with stubs. Replace the stubs in `app/` with real implementations when you're ready.
