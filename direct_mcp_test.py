#!/usr/bin/env python3
"""
Direct test of RAG MCP server using the HTTP transport.
This bypasses the session management and directly tests the functionality.
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, '/app')
sys.path.insert(0, './app')

try:
    from app.config import ServerConfig
    from app.orchestrator import Orchestrator
    from app.models import QueryResult
except ImportError as e:
    print(f"Import error: {e}")
    print("This script should be run from the project root or with proper Python path")
    sys.exit(1)


async def test_rag_functionality():
    """Test RAG functionality directly using the orchestrator."""
    print("🔍 Direct RAG MCP Server Test - Document Query")
    print("=" * 60)
    
    try:
        # Load configuration
        print("1. Loading configuration...")
        config = ServerConfig()
        print(f"✅ Configuration loaded")
        print(f"   Qdrant URL: {config.qdrant_url}")
        print(f"   Collection: {config.qdrant_collection_name}")
        print(f"   CSV directory: {config.csv_data_directory}")
        
        # Initialize orchestrator
        print("\n2. Initializing orchestrator...")
        orchestrator = Orchestrator(config)
        
        # Ensure Qdrant collection exists
        await orchestrator.qdrant_client.ensure_collection(
            collection_name=config.qdrant_collection_name,
            vector_size=384  # Default for all-MiniLM-L6-v2
        )
        print("✅ Orchestrator initialized and Qdrant collection ready")
        
        # Check server health
        print("\n3. Checking server health...")
        health_status = await orchestrator.health_check()
        print(f"✅ Health check completed:")
        for component, status in health_status.items():
            print(f"   - {component}: {status}")
        
        # Ingest sample data
        print("\n4. Ingesting sample CSV data...")
        csv_file_path = "./sample_data.csv"
        
        if not os.path.exists(csv_file_path):
            print(f"❌ Sample data file not found: {csv_file_path}")
            print("Creating sample data...")
            
            # Create sample data
            sample_data = """id,title,content,category
1,"Lunch Recipes","I love lunch! Here are some great lunch recipes including sandwiches, salads, and soups. Lunch is the best meal of the day.","food"
2,"Breakfast Ideas","Morning meals are important. Try eggs, toast, and coffee for a great start to your day.","food"
3,"Dinner Planning","Evening meals should be hearty. Consider pasta, meat, and vegetables for dinner.","food"
4,"Lunch Meeting Tips","Business lunches are great for networking. I love lunch meetings because they combine food and work.","business"
5,"Healthy Eating","Nutrition is important for all meals. Lunch should include proteins, vegetables, and grains.","health"
6,"Lunch Break Stories","Taking lunch breaks is essential. I love lunch because it gives me energy for the afternoon.","lifestyle"
7,"Restaurant Reviews","Great lunch spots in the city. I love lunch at these restaurants because of their amazing food.","reviews"
"""
            
            with open(csv_file_path, 'w') as f:
                f.write(sample_data)
            print(f"✅ Sample data created: {csv_file_path}")
        
        try:
            ingestion_result = await orchestrator.ingest_csv(csv_file_path)
            print(f"✅ Ingestion completed:")
            print(f"   Status: {ingestion_result.status}")
            print(f"   Documents processed: {ingestion_result.documents_processed}")
            print(f"   Chunks created: {ingestion_result.chunks_created}")
            print(f"   Embeddings generated: {ingestion_result.embeddings_generated}")
            
            if ingestion_result.errors:
                print(f"   Errors: {ingestion_result.errors}")
                
        except Exception as e:
            print(f"⚠️  Ingestion failed: {str(e)}")
            print("   Continuing with existing data...")
        
        # Query documents
        print("\n5. Querying documents for 'i love lunch' (max 5 results)...")
        
        try:
            query_results = await orchestrator.query(
                query="i love lunch",
                max_results=5,
                score_threshold=None
            )
            
            print(f"\n✅ Query completed successfully!")
            print(f"📊 Found {len(query_results)} results:")
            print("-" * 60)
            
            if not query_results:
                print("   No documents found matching your query.")
                print("   This might indicate:")
                print("   - The vector database is empty")
                print("   - The query doesn't match any indexed content")
                print("   - There's an issue with the embedding model")
            else:
                for i, result in enumerate(query_results, 1):
                    print(f"\n📄 Result {i}:")
                    print(f"   Score: {result.score:.4f}")
                    print(f"   Content: {result.content[:200]}...")
                    if result.metadata:
                        print(f"   Metadata: {result.metadata}")
                        
        except Exception as e:
            print(f"❌ Query failed: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Test another query
        print("\n6. Testing another query: 'business meeting' (max 3 results)...")
        
        try:
            query_results2 = await orchestrator.query(
                query="business meeting",
                max_results=3,
                score_threshold=0.1
            )
            
            print(f"\n✅ Second query completed!")
            print(f"📊 Found {len(query_results2)} results:")
            print("-" * 40)
            
            for i, result in enumerate(query_results2, 1):
                print(f"\n📄 Result {i}:")
                print(f"   Score: {result.score:.4f}")
                print(f"   Content: {result.content[:150]}...")
                
        except Exception as e:
            print(f"❌ Second query failed: {str(e)}")
        
        # Clean up
        print("\n7. Cleaning up...")
        await orchestrator.close()
        print("✅ Cleanup completed")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_rag_functionality())