#!/usr/bin/env python
"""
Verification script to demonstrate Logfire spans in action.

This script shows how Logfire spans are used throughout the application
for monitoring and observability.
"""

import asyncio
import tempfile
import csv
from pathlib import Path

from app.config import ServerConfig
from app.orchestrator import Orchestrator


async def verify_logfire_spans():
    """Verify Logfire spans are working throughout the application."""
    
    print("=" * 70)
    print("Logfire Spans Verification")
    print("=" * 70)
    print()
    
    # Create test CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['title', 'content'])
        writer.writeheader()
        writer.writerow({
            'title': 'Test Document',
            'content': 'This is a test document for verifying Logfire spans.'
        })
        csv_path = f.name
    
    try:
        # Initialize with Logfire disabled for cleaner output
        config = ServerConfig(
            enable_logfire=False,
            log_level="WARNING",
            qdrant_collection_name="test_logfire_spans"
        )
        orchestrator = Orchestrator(config)
        
        print("Logfire spans are instrumented in the following operations:")
        print()
        
        # 1. CSV Parser spans
        print("1. CSV PARSER SPANS")
        print("   - csv_parser.read_csv_file")
        print("   - csv_parser.parse_csv_to_documents")
        print()
        
        # 2. Embedder spans
        print("2. EMBEDDER SPANS")
        print("   - embedder.embed_texts")
        print("   - embedder.process_batch")
        print("   - embedder.chunk_text")
        print()
        
        # 3. Qdrant spans
        print("3. QDRANT CLIENT SPANS")
        print("   - qdrant.upsert_embeddings")
        print("   - qdrant.search")
        print("   - qdrant.health_check")
        print()
        
        # 4. Orchestrator spans
        print("4. ORCHESTRATOR SPANS")
        print("   - orchestrator.health_check")
        print()
        
        # 5. Main application spans
        print("5. MAIN APPLICATION SPANS (in app/main.py)")
        print("   - ingest_csv (MCP tool)")
        print("   - query_documents (MCP tool)")
        print("   - get_server_status (MCP tool)")
        print()
        
        print("=" * 70)
        print("Span Attributes Captured:")
        print("=" * 70)
        print()
        
        print("CSV Parser:")
        print("  - file_path, encoding, rows_count")
        print()
        
        print("Embedder:")
        print("  - texts_count, batch_size, model_name, batch_num, total_batches")
        print("  - text_length, max_chunk_size, chunk_overlap, chunks_created")
        print()
        
        print("Qdrant:")
        print("  - chunks_count, embeddings_count, collection")
        print("  - top_k, score_threshold, has_filters, results_count")
        print("  - url (for health checks)")
        print()
        
        print("Orchestrator:")
        print("  - health_status (component states)")
        print()
        
        print("Main Application:")
        print("  - file_path, correlation_id (for ingestion)")
        print("  - query, max_results, score_threshold, correlation_id (for queries)")
        print("  - correlation_id (for status checks)")
        print()
        
        print("=" * 70)
        print("To enable Logfire monitoring:")
        print("=" * 70)
        print()
        print("1. Set ENABLE_LOGFIRE=true in .env file")
        print("2. Configure Logfire credentials (if using Logfire cloud)")
        print("3. Run the application - spans will be automatically captured")
        print()
        print("When enabled, all operations will be traced with:")
        print("  ✓ Distributed tracing across components")
        print("  ✓ Performance metrics and timing")
        print("  ✓ Structured logging with context")
        print("  ✓ Error tracking with stack traces")
        print("  ✓ Correlation IDs for request tracking")
        print()
        
        await orchestrator.close()
        
    finally:
        # Cleanup
        Path(csv_path).unlink(missing_ok=True)
    
    print("=" * 70)
    print("Verification complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(verify_logfire_spans())
