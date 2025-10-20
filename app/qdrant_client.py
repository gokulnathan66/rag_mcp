"""
Qdrant vector database component for storing and retrieving document embeddings.

This module provides:
- Qdrant client initialization and connection management
- Collection creation and configuration with proper schema
- Vector storage operations with batch upsert support
- Similarity search functionality with configurable parameters
"""

from typing import List, Dict, Any, Optional
import logging

import logfire
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    SearchRequest,
    Filter,
    FieldCondition,
    MatchValue,
    ScoredPoint
)
from app.models import QdrantPoint, QueryResult, DocumentEmbedding, DocumentChunk

logger = logging.getLogger(__name__)


class QdrantClient:
    """
    Qdrant vector database client for managing document embeddings.
    
    Provides methods for:
    - Collection management and schema configuration
    - Batch vector storage operations
    - Similarity search with metadata filtering
    """
    
    def __init__(
        self, 
        url: str = "http://localhost:6333", 
        api_key: Optional[str] = None,
        collection_name: str = "firestore_documents",
        vector_size: int = 384  # Default for all-MiniLM-L6-v2
    ):
        """
        Initialize Qdrant client with connection parameters.
        
        Args:
            url: Qdrant server URL
            api_key: Optional API key for authentication
            collection_name: Default collection name for operations
            vector_size: Dimension of embedding vectors
        """
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.vector_size = vector_size
        
        # Initialize async Qdrant client
        self.client = AsyncQdrantClient(
            url=url,
            api_key=api_key,
            timeout=30.0
        )
        
        logger.info(f"Initialized Qdrant client for {url}")
    
    async def ensure_collection(
        self,
        collection_name: Optional[str] = None,
        vector_size: Optional[int] = None,
        distance: Distance = Distance.COSINE
    ) -> bool:
        """
        Ensure collection exists, create if it doesn't.
        
        Args:
            collection_name: Name of the collection (uses default if None)
            vector_size: Size of vectors (uses default if None)
            distance: Distance metric for similarity (COSINE, EUCLID, DOT)
            
        Returns:
            True if collection exists or was created successfully
        """
        collection_name = collection_name or self.collection_name
        vector_size = vector_size or self.vector_size
        
        try:
            # Check if collection exists
            collections = await self.client.get_collections()
            collection_exists = any(
                col.name == collection_name 
                for col in collections.collections
            )
            
            if collection_exists:
                logger.info(f"Collection '{collection_name}' already exists")
                return True
            
            # Create collection with vector configuration
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance
                )
            )
            
            logger.info(
                f"Created collection '{collection_name}' with vector size {vector_size}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring collection '{collection_name}': {e}")
            raise
    
    async def get_collection_info(
        self,
        collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get information about a collection.
        
        Args:
            collection_name: Name of the collection (uses default if None)
            
        Returns:
            Dictionary with collection information
        """
        collection_name = collection_name or self.collection_name
        
        try:
            info = await self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
                "config": {
                    "vector_size": info.config.params.vectors.size,
                    "distance": info.config.params.vectors.distance
                }
            }
        except Exception as e:
            logger.error(f"Error getting collection info for '{collection_name}': {e}")
            raise
    
    async def upsert_points(
        self,
        points: List[QdrantPoint],
        collection_name: Optional[str] = None,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Store or update document embeddings as vectors in Qdrant.
        Implements batch upsert operations for performance.
        
        Args:
            points: List of QdrantPoint objects to upsert
            collection_name: Target collection name (uses default if None)
            batch_size: Number of points to upsert per batch
            
        Returns:
            Dictionary with operation status and count
        """
        collection_name = collection_name or self.collection_name
        
        if not points:
            return {"status": "ok", "count": 0}
        
        try:
            # Ensure collection exists before upserting
            await self.ensure_collection(collection_name)
            
            # Convert QdrantPoint models to PointStruct
            point_structs = []
            for point in points:
                point_struct = PointStruct(
                    id=point.id,
                    vector=point.vector if isinstance(point.vector, list) else point.vector.get("dense", []),
                    payload=point.payload
                )
                point_structs.append(point_struct)
            
            # Batch upsert for performance
            total_upserted = 0
            for i in range(0, len(point_structs), batch_size):
                batch = point_structs[i:i + batch_size]
                
                await self.client.upsert(
                    collection_name=collection_name,
                    points=batch,
                    wait=True  # Wait for operation to complete
                )
                
                total_upserted += len(batch)
                logger.debug(f"Upserted batch {i//batch_size + 1}: {len(batch)} points")
            
            logger.info(
                f"Successfully upserted {total_upserted} points to '{collection_name}'"
            )
            
            return {
                "status": "ok",
                "count": total_upserted,
                "collection": collection_name
            }
            
        except Exception as e:
            logger.error(f"Error upserting points to '{collection_name}': {e}")
            raise
    
    async def upsert_embeddings(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[DocumentEmbedding],
        collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convenience method to upsert document chunks with their embeddings.
        
        Args:
            chunks: List of DocumentChunk objects
            embeddings: List of DocumentEmbedding objects
            collection_name: Target collection name (uses default if None)
            
        Returns:
            Dictionary with operation status and count
        """
        with logfire.span(
            "qdrant.upsert_embeddings",
            chunks_count=len(chunks),
            embeddings_count=len(embeddings),
            collection=collection_name or self.collection_name
        ):
            if len(chunks) != len(embeddings):
                raise ValueError("Number of chunks must match number of embeddings")
            
            # Create QdrantPoint objects from chunks and embeddings
            points = []
            for chunk, embedding in zip(chunks, embeddings):
                payload = {
                    "document_id": chunk.parent_document_id,
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "embedding_model": embedding.model_name,
                    **chunk.metadata  # Include any additional metadata
                }
                
                point = QdrantPoint(
                    id=chunk.chunk_id,
                    vector=embedding.vector,
                    payload=payload
                )
                points.append(point)
            
            result = await self.upsert_points(points, collection_name)
            logfire.info(
                "Embeddings upserted to Qdrant",
                points_count=result.get("count", 0),
                collection=result.get("collection")
            )
            return result
    
    async def search(
        self,
        query_vector: List[float],
        collection_name: Optional[str] = None,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search to find documents similar to query vector.
        
        Args:
            query_vector: Query embedding vector
            collection_name: Collection to search (uses default if None)
            top_k: Maximum number of results to return
            score_threshold: Minimum similarity score threshold
            filter_conditions: Optional metadata filters
            
        Returns:
            List of search results with similarity scores and metadata
        """
        collection_name = collection_name or self.collection_name
        
        with logfire.span(
            "qdrant.search",
            collection=collection_name,
            top_k=top_k,
            score_threshold=score_threshold,
            has_filters=filter_conditions is not None
        ):
            try:
                # Build filter if conditions provided
                query_filter = None
                if filter_conditions:
                    query_filter = self._build_filter(filter_conditions)
                
                # Perform similarity search
                results = await self.client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=top_k,
                    score_threshold=score_threshold,
                    query_filter=query_filter,
                    with_payload=True,
                    with_vectors=False  # Don't return vectors to save bandwidth
                )
                
                # Convert results to dictionaries
                search_results = []
                for result in results:
                    search_results.append({
                        "id": result.id,
                        "score": result.score,
                        "payload": result.payload
                    })
                
                logger.info(
                    f"Search returned {len(search_results)} results from '{collection_name}'"
                )
                logfire.info(
                    "Qdrant search completed",
                    results_count=len(search_results),
                    collection=collection_name
                )
                
                return search_results
                
            except Exception as e:
                logger.error(f"Error searching collection '{collection_name}': {e}")
                logfire.error("Qdrant search failed", collection=collection_name, error=str(e))
                raise
    
    async def search_documents(
        self,
        query_vector: List[float],
        collection_name: Optional[str] = None,
        top_k: int = 10,
        score_threshold: Optional[float] = None
    ) -> List[QueryResult]:
        """
        Search for documents and return structured QueryResult objects.
        
        Args:
            query_vector: Query embedding vector
            collection_name: Collection to search (uses default if None)
            top_k: Maximum number of results to return
            score_threshold: Minimum similarity score threshold
            
        Returns:
            List of QueryResult objects with document information
        """
        results = await self.search(
            query_vector=query_vector,
            collection_name=collection_name,
            top_k=top_k,
            score_threshold=score_threshold
        )
        
        # Convert to QueryResult objects
        query_results = []
        for result in results:
            payload = result["payload"]
            
            # Note: This creates a minimal firestore_metadata
            # In production, you'd fetch the full document from Firestore
            from app.models import FirestoreDocument
            from datetime import datetime
            
            firestore_metadata = FirestoreDocument(
                document_id=payload.get("document_id", ""),
                collection_path=payload.get("collection_path", "unknown"),
                content={"chunk_content": payload.get("content", "")},
                create_time=datetime.utcnow(),
                update_time=datetime.utcnow()
            )
            
            query_result = QueryResult(
                document_id=payload.get("document_id", ""),
                chunk_id=payload.get("chunk_id", result["id"]),
                content=payload.get("content", ""),
                similarity_score=result["score"],
                metadata=payload,
                firestore_metadata=firestore_metadata
            )
            query_results.append(query_result)
        
        return query_results
    
    async def delete_point(
        self,
        point_id: str,
        collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete a single point from the collection.
        
        Args:
            point_id: ID of the point to delete
            collection_name: Collection name (uses default if None)
            
        Returns:
            Dictionary with operation status
        """
        collection_name = collection_name or self.collection_name
        
        try:
            await self.client.delete(
                collection_name=collection_name,
                points_selector=[point_id],
                wait=True
            )
            
            logger.info(f"Deleted point '{point_id}' from '{collection_name}'")
            
            return {"status": "ok", "deleted_id": point_id}
            
        except Exception as e:
            logger.error(f"Error deleting point '{point_id}': {e}")
            raise
    
    async def delete_by_document_id(
        self,
        document_id: str,
        collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete all chunks associated with a document.
        
        Args:
            document_id: Parent document ID
            collection_name: Collection name (uses default if None)
            
        Returns:
            Dictionary with operation status and count
        """
        collection_name = collection_name or self.collection_name
        
        try:
            # Delete all points with matching document_id in payload
            await self.client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                ),
                wait=True
            )
            
            logger.info(
                f"Deleted all chunks for document '{document_id}' from '{collection_name}'"
            )
            
            return {"status": "ok", "document_id": document_id}
            
        except Exception as e:
            logger.error(f"Error deleting document '{document_id}': {e}")
            raise
    
    def _build_filter(self, conditions: Dict[str, Any]) -> Filter:
        """
        Build Qdrant filter from condition dictionary.
        
        Args:
            conditions: Dictionary of field:value conditions
            
        Returns:
            Qdrant Filter object
        """
        must_conditions = []
        
        for field, value in conditions.items():
            condition = FieldCondition(
                key=field,
                match=MatchValue(value=value)
            )
            must_conditions.append(condition)
        
        return Filter(must=must_conditions)
    
    async def health_check(self) -> bool:
        """
        Check if Qdrant server is accessible and healthy.
        
        Returns:
            True if server is healthy, False otherwise
        """
        with logfire.span("qdrant.health_check", url=self.url):
            try:
                # Try to get collections as a health check
                await self.client.get_collections()
                logger.info("Qdrant health check passed")
                logfire.info("Qdrant health check passed", url=self.url)
                return True
            except Exception as e:
                logger.error(f"Qdrant health check failed: {e}")
                logfire.error("Qdrant health check failed", url=self.url, error=str(e))
                return False
    
    async def close(self):
        """Close the Qdrant client connection."""
        try:
            await self.client.close()
            logger.info("Closed Qdrant client connection")
        except Exception as e:
            logger.error(f"Error closing Qdrant client: {e}")
