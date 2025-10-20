"""
Web API for CSV upload and document querying.

This module provides HTTP endpoints for:
- Uploading CSV files for ingestion
- Querying documents via web interface
- Serving the frontend UI
"""

import logging
from pathlib import Path
from typing import Optional
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ServerConfig
from .orchestrator import Orchestrator
from .models import QueryResult, IngestionStatus


logger = logging.getLogger(__name__)


# Request/Response Models
class QueryRequest(BaseModel):
    """Request model for document queries."""
    query: str = Field(..., description="Natural language query")
    max_results: int = Field(default=10, ge=1, le=100, description="Maximum results")
    score_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class UploadResponse(BaseModel):
    """Response model for CSV upload."""
    status: str
    message: str
    file_path: str
    ingestion_result: Optional[IngestionStatus] = None


def create_web_api(orchestrator: Orchestrator, config: ServerConfig) -> FastAPI:
    """
    Create FastAPI web application for CSV upload and querying.
    
    Args:
        orchestrator: Orchestrator instance for processing
        config: Server configuration
        
    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="RAG MCP Server Web UI",
        description="Web interface for CSV ingestion and document querying",
        version="1.0.0"
    )
    
    # Create upload directory
    upload_dir = Path(config.csv_data_directory) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Serve static files (frontend)
    frontend_dir = Path(__file__).parent / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
    
    @app.get("/", response_class=HTMLResponse)
    async def serve_frontend():
        """Serve the main frontend HTML page."""
        frontend_file = frontend_dir / "index.html"
        if frontend_file.exists():
            return frontend_file.read_text()
        return """
        <html>
            <body>
                <h1>RAG MCP Server</h1>
                <p>Frontend not found. Please ensure frontend files are in app/frontend/</p>
            </body>
        </html>
        """
    
    @app.post("/api/upload-csv", response_model=UploadResponse)
    async def upload_csv(file: UploadFile = File(...)):
        """
        Upload and ingest a CSV file.
        
        Args:
            file: Uploaded CSV file
            
        Returns:
            Upload response with ingestion status
        """
        try:
            # Validate file type
            if not file.filename.endswith('.csv'):
                raise HTTPException(
                    status_code=400,
                    detail="Only CSV files are supported"
                )
            
            # Save uploaded file
            file_path = upload_dir / file.filename
            logger.info(f"Saving uploaded file to: {file_path}")
            
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            logger.info(f"File saved successfully: {file_path}")
            
            # Ingest the CSV file
            logger.info(f"Starting ingestion for: {file_path}")
            ingestion_result = await orchestrator.ingest_csv(str(file_path))
            
            logger.info(f"Ingestion completed: {ingestion_result.status}")
            
            return UploadResponse(
                status="success",
                message=f"File '{file.filename}' uploaded and ingested successfully",
                file_path=str(file_path),
                ingestion_result=ingestion_result
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading CSV: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload and ingest CSV: {str(e)}"
            )
    
    @app.post("/api/query", response_model=list[QueryResult])
    async def query_documents(request: QueryRequest):
        """
        Query documents using natural language.
        
        Args:
            request: Query request with search parameters
            
        Returns:
            List of matching documents with similarity scores
        """
        try:
            logger.info(f"Processing query: {request.query[:50]}...")
            
            results = await orchestrator.query(
                query=request.query,
                max_results=request.max_results,
                score_threshold=request.score_threshold
            )
            
            logger.info(f"Query returned {len(results)} results")
            
            return results
            
        except Exception as e:
            logger.error(f"Error querying documents: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to query documents: {str(e)}"
            )
    
    @app.get("/api/health")
    async def health_check():
        """Check health of all components."""
        try:
            health_status = await orchestrator.health_check()
            
            # Determine overall health
            all_healthy = all(status == "ok" for status in health_status.values())
            
            return {
                "status": "healthy" if all_healthy else "degraded",
                "components": health_status
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "error": str(e)
                }
            )
    
    @app.get("/api/uploaded-files")
    async def list_uploaded_files():
        """List all uploaded CSV files."""
        try:
            files = []
            for file_path in upload_dir.glob("*.csv"):
                stat = file_path.stat()
                files.append({
                    "filename": file_path.name,
                    "size_bytes": stat.st_size,
                    "uploaded_at": stat.st_mtime
                })
            
            return {"files": files}
            
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list files: {str(e)}"
            )
    
    logger.info("Web API created successfully")
    return app
