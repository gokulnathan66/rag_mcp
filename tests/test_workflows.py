"""
Integration tests for LangGraph orchestration workflows.

Tests the CSV ingestion and query processing workflows.
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import csv

from app.config import ServerConfig
from app.orchestrator import Orchestrator


@pytest.fixture
def test_config():
    """Create a test configuration."""
    return ServerConfig(
        csv_data_directory="./test_data",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="test_rag_collection",
        embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
        max_chunk_size=500,
        chunk_overlap=100,
        enable_logfire=False,
        log_level="INFO"
    )


@pytest.fixture
def sample_csv_file():
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['title', 'content', 'category'])
        writer.writeheader()
        writer.writerow({
            'title': 'Test Document 1',
            'content': 'This is a test document about machine learning and artificial intelligence.',
            'category': 'technology'
        })
        writer.writerow({
            'title': 'Test Document 2',
            'content': 'This document discusses natural language processing and text embeddings.',
            'category': 'technology'
        })
        writer.writerow({
            'title': 'Test Document 3',
            'content': 'A guide to vector databases and similarity search techniques.',
            'category': 'database'
        })
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_csv_ingestion_workflow(test_config, sample_csv_file):
    """Test the CSV ingestion workflow end-to-end."""
    orchestrator = Orchestrator(test_config)
    
    try:
        # Run ingestion
        result = await orchestrator.ingest_csv(sample_csv_file)
        
        # Verify results
        assert result.status in ["success", "partial"], f"Ingestion failed: {result.errors}"
        assert result.documents_processed == 3, "Should process 3 documents"
        assert result.chunks_created > 0, "Should create at least one chunk"
        assert result.embeddings_generated > 0, "Should generate embeddings"
        assert result.processing_time_seconds is not None
        
        print(f"✓ Ingestion successful: {result.documents_processed} docs, {result.chunks_created} chunks")
        
    finally:
        await orchestrator.close()


@pytest.mark.asyncio
async def test_query_workflow(test_config, sample_csv_file):
    """Test the query processing workflow end-to-end."""
    orchestrator = Orchestrator(test_config)
    
    try:
        # First ingest some data
        await orchestrator.ingest_csv(sample_csv_file)
        
        # Now query
        results = await orchestrator.query(
            query="machine learning and AI",
            max_results=5
        )
        
        # Verify results
        assert isinstance(results, list), "Results should be a list"
        assert len(results) > 0, "Should return at least one result"
        
        # Check result structure
        for result in results:
            assert hasattr(result, 'document_id')
            assert hasattr(result, 'chunk_id')
            assert hasattr(result, 'content')
            assert hasattr(result, 'similarity_score')
            assert 0.0 <= result.similarity_score <= 1.0
        
        print(f"✓ Query successful: {len(results)} results returned")
        print(f"  Top result score: {results[0].similarity_score:.4f}")
        
    finally:
        await orchestrator.close()


@pytest.mark.asyncio
async def test_health_check(test_config):
    """Test orchestrator health check."""
    orchestrator = Orchestrator(test_config)
    
    try:
        health = await orchestrator.health_check()
        
        assert "csv_parser" in health
        assert "embedder" in health
        assert "qdrant" in health
        
        print(f"✓ Health check: {health}")
        
    finally:
        await orchestrator.close()


def test_ingestion_sync(test_config, sample_csv_file):
    """Synchronous wrapper for ingestion test."""
    asyncio.run(test_csv_ingestion_workflow(test_config, sample_csv_file))


def test_query_sync(test_config, sample_csv_file):
    """Synchronous wrapper for query test."""
    asyncio.run(test_query_workflow(test_config, sample_csv_file))
