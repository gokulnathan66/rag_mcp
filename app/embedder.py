"""
FastEmbed processing component for generating embeddings and chunking documents.

This module provides:
- FastEmbed initialization with ONNX optimization
- Document and query embedding generation
- Text chunking with configurable strategies
"""

from typing import List, Dict, Any, Optional
from fastembed import TextEmbedding
from app.models import DocumentChunk, DocumentEmbedding
import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid


class TextChunker:
    """
    Text chunking utility for splitting large documents into manageable chunks.
    Implements chunking with configurable overlap for better context preservation.
    """
    
    def __init__(self, max_chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialize the text chunker.
        
        Args:
            max_chunk_size: Maximum number of characters per chunk
            chunk_overlap: Number of characters to overlap between chunks
        """
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(
        self, 
        text: str, 
        parent_document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Split text into chunks with overlap.
        
        Args:
            text: Text content to chunk
            parent_document_id: ID of the parent document
            metadata: Additional metadata to include in chunks
            
        Returns:
            List of DocumentChunk objects
        """
        if not text or not text.strip():
            return []
        
        chunks = []
        metadata = metadata or {}
        
        # If text is smaller than max chunk size, return as single chunk
        if len(text) <= self.max_chunk_size:
            chunk = DocumentChunk(
                chunk_id=str(uuid.uuid4()),
                parent_document_id=parent_document_id,
                content=text,
                chunk_index=0,
                metadata=metadata
            )
            return [chunk]
        
        # Split text into chunks with overlap
        start = 0
        chunk_index = 0
        
        while start < len(text):
            # Calculate end position for this chunk
            end = start + self.max_chunk_size
            
            # If this is not the last chunk, try to break at a sentence or word boundary
            if end < len(text):
                # Look for sentence boundaries (., !, ?)
                sentence_end = max(
                    text.rfind('. ', start, end),
                    text.rfind('! ', start, end),
                    text.rfind('? ', start, end)
                )
                
                if sentence_end > start:
                    end = sentence_end + 1
                else:
                    # Look for word boundary (space)
                    word_end = text.rfind(' ', start, end)
                    if word_end > start:
                        end = word_end
            
            # Extract chunk content
            chunk_content = text[start:end].strip()
            
            if chunk_content:
                chunk = DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    parent_document_id=parent_document_id,
                    content=chunk_content,
                    chunk_index=chunk_index,
                    metadata=metadata
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # Move start position, accounting for overlap
            start = end - self.chunk_overlap if end < len(text) else end
            
            # Ensure we make progress
            if start <= chunks[-1].content.find(chunk_content) if chunks else 0:
                start = end
        
        return chunks


class Embedder:
    """
    FastEmbed-based embedding generator with ONNX optimization.
    
    Provides methods for generating embeddings for documents and queries
    with batch processing support for performance optimization.
    """
    
    def __init__(
        self, 
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 32,
        enable_sparse: bool = False,
        max_chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize FastEmbed with ONNX optimization.
        
        Args:
            model_name: Name of the FastEmbed model to use
            batch_size: Batch size for embedding generation
            enable_sparse: Whether to enable sparse embeddings (not yet implemented)
            max_chunk_size: Maximum size for text chunks
            chunk_overlap: Overlap between chunks
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.enable_sparse = enable_sparse
        
        # Initialize FastEmbed with ONNX optimization
        # FastEmbed automatically uses ONNX runtime for CPU optimization
        self.embedding_model = TextEmbedding(
            model_name=model_name,
            max_length=512  # Standard max length for most models
        )
        
        # Initialize text chunker
        self.chunker = TextChunker(
            max_chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # Thread pool for running synchronous FastEmbed operations
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    async def embed_texts(
        self, 
        texts: List[str],
        embedding_type: str = "dense"
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts with batch processing.
        
        Args:
            texts: List of text strings to embed
            embedding_type: Type of embedding ("dense" or "sparse")
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Run FastEmbed in thread pool since it's synchronous
        loop = asyncio.get_event_loop()
        
        # Process in batches for better performance
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            # Generate embeddings for batch
            embeddings = await loop.run_in_executor(
                self._executor,
                self._generate_embeddings_sync,
                batch
            )
            
            all_embeddings.extend(embeddings)
        
        return all_embeddings
    
    def _generate_embeddings_sync(self, texts: List[str]) -> List[List[float]]:
        """
        Synchronous method to generate embeddings using FastEmbed.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        # FastEmbed returns a generator, convert to list
        embeddings = list(self.embedding_model.embed(texts))
        
        # Convert numpy arrays to lists
        return [embedding.tolist() for embedding in embeddings]
    
    async def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query text.
        
        Args:
            text: Query text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        embeddings = await self.embed_texts([text])
        return embeddings[0] if embeddings else []
    
    async def embed_documents(
        self,
        documents: List[DocumentChunk]
    ) -> List[DocumentEmbedding]:
        """
        Generate embeddings for a list of document chunks.
        
        Args:
            documents: List of DocumentChunk objects
            
        Returns:
            List of DocumentEmbedding objects
        """
        if not documents:
            return []
        
        # Extract text content from chunks
        texts = [doc.content for doc in documents]
        
        # Generate embeddings
        vectors = await self.embed_texts(texts)
        
        # Create DocumentEmbedding objects
        embeddings = []
        for doc, vector in zip(documents, vectors):
            embedding = DocumentEmbedding(
                chunk_id=doc.chunk_id,
                vector=vector,
                model_name=self.model_name,
                embedding_type="dense"
            )
            embeddings.append(embedding)
        
        return embeddings
    
    def chunk_text(
        self,
        text: str,
        parent_document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Chunk text into smaller segments with overlap.
        
        Args:
            text: Text to chunk
            parent_document_id: ID of the parent document
            metadata: Additional metadata for chunks
            
        Returns:
            List of DocumentChunk objects
        """
        return self.chunker.chunk_text(text, parent_document_id, metadata)
    
    async def chunk_and_embed(
        self,
        text: str,
        parent_document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> tuple[List[DocumentChunk], List[DocumentEmbedding]]:
        """
        Convenience method to chunk text and generate embeddings in one call.
        
        Args:
            text: Text to chunk and embed
            parent_document_id: ID of the parent document
            metadata: Additional metadata for chunks
            
        Returns:
            Tuple of (chunks, embeddings)
        """
        # Chunk the text
        chunks = self.chunk_text(text, parent_document_id, metadata)
        
        # Generate embeddings for chunks
        embeddings = await self.embed_documents(chunks)
        
        return chunks, embeddings
    
    def __del__(self):
        """Cleanup thread pool on deletion."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
