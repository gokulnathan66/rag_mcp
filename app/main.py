from fastapi import FastAPI

# Placeholder for FastMCP server; using FastAPI for a lightweight runner
app = FastAPI(title="RAG MCP Server - scaffold")

@app.get("/health")
async def health():
    return {"status": "ok"}
