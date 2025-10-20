# RAG MCP Server Makefile

.PHONY: server dev install test clean help

# Run the MCP server
server:
	python -m app.main

# Run the MCP server in development mode with auto-reload
dev:
	python -m app.main

# Install dependencies
install:
	pip install -e .

# Run tests
test:
	python -m pytest tests/ -v

# Clean up cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

# Show available commands
help:
	@echo "Available commands:"
	@echo "  server    - Run the RAG MCP server"
	@echo "  dev       - Run server in development mode"
	@echo "  install   - Install dependencies"
	@echo "  test      - Run tests"
	@echo "  clean     - Clean up cache files"
	@echo "  help      - Show this help message"