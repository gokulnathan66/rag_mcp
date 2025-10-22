# Getting Started Checklist

Use this checklist to get your RAG MCP Server Web UI up and running.

## ✅ Prerequisites

- [ ] Python 3.10 or higher installed
  ```bash
  python --version
  ```

- [ ] Docker installed and running
  ```bash
  docker --version
  docker ps
  ```

- [ ] Git installed (if cloning repository)
  ```bash
  git --version
  ```

## ✅ Installation Steps

### 1. Get the Code

- [ ] Clone or download the repository
  ```bash
  git clone <repository-url>
  cd rag_mcp
  ```

### 2. Install Python Dependencies

- [ ] Install required packages
  ```bash
  pip install -r requirements.txt
  ```

- [ ] Verify installation
  ```bash
  python -c "import fastapi, uvicorn, qdrant_client, fastembed; print('✓ All dependencies installed')"
  ```

### 3. Start Qdrant Database

- [ ] Start Qdrant using Docker Compose
  ```bash
  docker-compose up -d qdrant
  ```

- [ ] Wait for Qdrant to be ready (5-10 seconds)
  ```bash
  sleep 5
  ```

- [ ] Verify Qdrant is running
  ```bash
  curl http://localhost:6333/health
  # Should return: {"title":"qdrant - vector search engine","version":"..."}
  ```

- [ ] Optional: Check Qdrant dashboard
  ```
  Open: http://localhost:6333/dashboard
  ```

### 4. Create Data Directory

- [ ] Create uploads directory
  ```bash
  mkdir -p data/uploads
  ```

- [ ] Verify directory exists
  ```bash
  ls -la data/
  ```

## ✅ Start the Web UI

### Option A: Using Startup Script (Easiest)

- [ ] Make script executable (Linux/Mac)
  ```bash
  chmod +x start_web_ui.sh
  ```

- [ ] Run the script
  ```bash
  ./start_web_ui.sh
  ```

### Option B: Using Make

- [ ] Start web UI
  ```bash
  make web-ui
  ```

### Option C: Direct Python Command

- [ ] Start web server
  ```bash
  python -m app.web_server
  ```

### 5. Verify Web UI is Running

- [ ] Check server logs for "Starting web server" message

- [ ] Open browser to http://localhost:8080

- [ ] Verify page loads with "RAG MCP Server" title

- [ ] Check health status shows "✓ Healthy"

## ✅ Test with Sample Data

### 1. Upload Sample CSV

- [ ] Locate sample file: `data/sample_products.csv`

- [ ] In Web UI, click "Choose File"

- [ ] Select `sample_products.csv`

- [ ] Click "Upload & Index"

- [ ] Wait for processing to complete

- [ ] Verify success message with statistics:
  - Documents processed: 10
  - Chunks created: ~10-20
  - Embeddings generated: ~10-20

### 2. Test Queries

Try these sample queries:

- [ ] Query: "wireless devices"
  - Expected: Results about wireless mouse, charger, speaker

- [ ] Query: "office equipment"
  - Expected: Results about laptop stand, desk lamp, monitor arm

- [ ] Query: "electronics under $50"
  - Expected: Various electronic products

- [ ] Adjust "Max Results" to 5

- [ ] Try setting "Min Score" to 0.7

### 3. Verify Results

- [ ] Results show similarity scores (percentage)

- [ ] Content is displayed correctly

- [ ] Metadata shows source file and row number

- [ ] Results are ranked by relevance

## ✅ Upload Your Own Data

### 1. Prepare Your CSV

- [ ] CSV has headers in first row

- [ ] File uses UTF-8 encoding

- [ ] Delimiter is comma (or configure in .env)

- [ ] File size is reasonable (<10MB for testing)

### 2. Upload and Test

- [ ] Upload your CSV file

- [ ] Check ingestion statistics

- [ ] Try relevant queries for your data

- [ ] Verify results make sense

## ✅ Configuration (Optional)

### Create .env File

- [ ] Create `.env` file in project root
  ```bash
  touch .env
  ```

- [ ] Add custom configuration:
  ```bash
  # CSV Configuration
  CSV_DATA_DIRECTORY=./data
  CSV_DELIMITER=,
  CSV_ENCODING=utf-8
  
  # Qdrant Configuration
  QDRANT_URL=http://localhost:6333
  QDRANT_COLLECTION_NAME=csv_documents
  
  # Embedding Configuration
  EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
  EMBEDDING_BATCH_SIZE=32
  
  # Processing Configuration
  MAX_CHUNK_SIZE=1000
  CHUNK_OVERLAP=200
  
  # Logging
  LOG_LEVEL=INFO
  ```

- [ ] Restart web server to apply changes

## ✅ Docker Compose (Alternative)

If you prefer to run everything in Docker:

- [ ] Build and start all services
  ```bash
  docker-compose up -d
  ```

- [ ] Wait for services to start (10-15 seconds)

- [ ] Check logs
  ```bash
  docker-compose logs -f web-ui
  ```

- [ ] Access Web UI at http://localhost:8001 (note: port 8001)

- [ ] Verify Qdrant at http://localhost:6333/dashboard

## ✅ Troubleshooting

### If Qdrant won't start:

- [ ] Check if port 6333 is already in use
  ```bash
  lsof -i :6333  # Mac/Linux
  netstat -ano | findstr :6333  # Windows
  ```

- [ ] Stop conflicting service or change Qdrant port

- [ ] Check Docker logs
  ```bash
  docker-compose logs qdrant
  ```

### If Web UI won't start:

- [ ] Check if port 8080 is already in use
  ```bash
  lsof -i :8080  # Mac/Linux
  netstat -ano | findstr :8080  # Windows
  ```

- [ ] Use different port
  ```bash
  uvicorn app.web_api:app --host 0.0.0.0 --port 8080
  ```

- [ ] Check Python dependencies
  ```bash
  pip install -r requirements.txt --upgrade
  ```

### If upload fails:

- [ ] Check directory permissions
  ```bash
  ls -la data/uploads/
  chmod 755 data/uploads/
  ```

- [ ] Verify CSV format (headers, encoding)

- [ ] Check server logs for error details

### If queries return no results:

- [ ] Verify CSV was uploaded successfully

- [ ] Check Qdrant has vectors
  ```bash
  curl http://localhost:6333/collections/csv_documents
  ```

- [ ] Try broader queries

- [ ] Lower score threshold or remove it

## ✅ Next Steps

### Immediate:
- [ ] Read [QUICKSTART_WEB_UI.md](QUICKSTART_WEB_UI.md) for detailed guide
- [ ] Review [WEB_UI_SUMMARY.md](WEB_UI_SUMMARY.md) for features
- [ ] Check [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) for architecture

### Short Term:
- [ ] Upload your production CSV files
- [ ] Experiment with different queries
- [ ] Tune chunk size and overlap settings
- [ ] Monitor performance and health

### Long Term:
- [ ] Add authentication for production
- [ ] Configure CORS for your domain
- [ ] Set up monitoring and logging
- [ ] Deploy to production environment

## ✅ Verification Checklist

Before considering setup complete:

- [ ] Qdrant is running and healthy
- [ ] Web UI loads in browser
- [ ] Health status shows all components "ok"
- [ ] Sample CSV uploads successfully
- [ ] Queries return relevant results
- [ ] Results show similarity scores
- [ ] Uploaded files list is visible

## 🎉 Success!

If all items are checked, you're ready to use the RAG MCP Server Web UI!

### Quick Reference Commands

```bash
# Start everything
./start_web_ui.sh

# Or manually:
docker-compose up -d qdrant
python -m app.web_server

# Check health
curl http://localhost:8080/api/health

# View logs
docker-compose logs -f

# Stop everything
docker-compose down
```

### URLs to Bookmark

- Web UI: http://localhost:8080
- Qdrant Dashboard: http://localhost:6333/dashboard
- API Health: http://localhost:8080/api/health

### Support

If you encounter issues:
1. Check logs: `docker-compose logs -f`
2. Review troubleshooting section above
3. Check browser console for frontend errors
4. Verify all prerequisites are met

---

**Happy querying! 🚀**
