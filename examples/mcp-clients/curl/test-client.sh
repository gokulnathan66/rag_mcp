#!/bin/bash

# RAG MCP Server - curl Client Test Script
# 
# This script demonstrates how to interact with the RAG MCP Server
# using curl and the HTTP transport.

set -e

# Configuration
MCP_URL="${MCP_SERVER_URL:-http://localhost:8000/mcp/}"
HEALTH_URL="${MCP_HEALTH_URL:-http://localhost:8000/health}"
TIMEOUT=30
VERBOSE=${VERBOSE:-false}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to make MCP requests
mcp_request() {
    local method="$1"
    local tool_name="$2"
    local arguments="$3"
    local request_id=$(date +%s)
    
    local payload="{
        \"jsonrpc\": \"2.0\",
        \"id\": $request_id,
        \"method\": \"$method\",
        \"params\": {
            \"name\": \"$tool_name\",
            \"arguments\": $arguments
        }
    }"
    
    if [ "$VERBOSE" = "true" ]; then
        log_info "Making MCP request to: $MCP_URL"
        log_info "Payload: $payload"
    fi
    
    local response
    response=$(curl -s -X POST "$MCP_URL" \
        -H "Content-Type: application/json" \
        -m "$TIMEOUT" \
        -d "$payload")
    
    local curl_exit_code=$?
    
    if [ $curl_exit_code -ne 0 ]; then
        log_error "curl request failed with exit code: $curl_exit_code"
        return 1
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        log_info "Response: $response"
    fi
    
    # Check if response contains error
    if echo "$response" | jq -e '.error' > /dev/null 2>&1; then
        local error_code=$(echo "$response" | jq -r '.error.code // "UNKNOWN"')
        local error_message=$(echo "$response" | jq -r '.error.message // "Unknown error"')
        log_error "MCP Error [$error_code]: $error_message"
        return 1
    fi
    
    echo "$response"
}

# Function to check health
check_health() {
    log_info "Checking server health at: $HEALTH_URL"
    
    local response
    response=$(curl -s -X GET "$HEALTH_URL" -m 10)
    local curl_exit_code=$?
    
    if [ $curl_exit_code -ne 0 ]; then
        log_error "Health check failed with curl exit code: $curl_exit_code"
        return 1
    fi
    
    local status=$(echo "$response" | jq -r '.status // "unknown"')
    
    if [ "$status" = "healthy" ]; then
        log_success "Server is healthy"
    elif [ "$status" = "degraded" ]; then
        log_warning "Server is degraded"
    else
        log_error "Server is unhealthy (status: $status)"
        return 1
    fi
    
    echo "$response"
}

# Test functions
test_connection() {
    log_info "Testing connection to RAG MCP Server"
    log_info "MCP URL: $MCP_URL"
    log_info "Health URL: $HEALTH_URL"
    echo
    
    # Check health endpoint
    log_info "Step 1: Checking health endpoint..."
    if health_result=$(check_health); then
        log_success "Health check passed"
        if [ "$VERBOSE" = "true" ]; then
            echo "$health_result" | jq '.'
        fi
    else
        log_error "Health check failed"
        return 1
    fi
    echo
    
    # Check server status via MCP
    log_info "Step 2: Checking server status via MCP..."
    if status_result=$(mcp_request "tools/call" "get_server_status" "{}"); then
        log_success "Server status check passed"
        
        local server_name=$(echo "$status_result" | jq -r '.result.server_name // "unknown"')
        local version=$(echo "$status_result" | jq -r '.result.version // "unknown"')
        local status=$(echo "$status_result" | jq -r '.result.status // "unknown"')
        
        log_info "Server: $server_name v$version"
        log_info "Status: $status"
        
        if [ "$VERBOSE" = "true" ]; then
            echo "$status_result" | jq '.'
        fi
    else
        log_error "Server status check failed"
        return 1
    fi
    echo
    
    log_success "All connection tests passed!"
    return 0
}

# Tool-specific functions
get_server_status() {
    log_info "Getting server status..."
    if result=$(mcp_request "tools/call" "get_server_status" "{}"); then
        echo "$result" | jq '.'
    else
        log_error "Failed to get server status"
        return 1
    fi
}

get_health_status() {
    log_info "Getting health status..."
    if result=$(check_health); then
        echo "$result" | jq '.'
    else
        log_error "Failed to get health status"
        return 1
    fi
}

ingest_csv() {
    local file_path="$1"
    
    if [ -z "$file_path" ]; then
        log_error "File path is required"
        echo "Usage: $0 ingest <file_path>"
        return 1
    fi
    
    log_info "Ingesting CSV file: $file_path"
    
    local arguments="{\"file_path\": \"$file_path\"}"
    
    if result=$(mcp_request "tools/call" "ingest_csv" "$arguments"); then
        log_success "CSV ingestion completed"
        echo "$result" | jq '.'
    else
        log_error "CSV ingestion failed"
        return 1
    fi
}

query_documents() {
    local query_text="$1"
    local max_results="${2:-10}"
    local score_threshold="$3"
    
    if [ -z "$query_text" ]; then
        log_error "Query text is required"
        echo "Usage: $0 query <query_text> [max_results] [score_threshold]"
        return 1
    fi
    
    log_info "Querying documents: $query_text"
    log_info "Max results: $max_results"
    
    local arguments="{\"query\": \"$query_text\", \"max_results\": $max_results"
    
    if [ -n "$score_threshold" ]; then
        arguments="$arguments, \"score_threshold\": $score_threshold"
        log_info "Score threshold: $score_threshold"
    fi
    
    arguments="$arguments}"
    
    if result=$(mcp_request "tools/call" "query_documents" "$arguments"); then
        log_success "Document query completed"
        
        local result_count=$(echo "$result" | jq '.result | length')
        log_info "Found $result_count results"
        
        echo "$result" | jq '.'
    else
        log_error "Document query failed"
        return 1
    fi
}

# Interactive mode
interactive_mode() {
    log_info "Starting interactive mode"
    log_info "Type 'help' for available commands, 'quit' to exit"
    echo
    
    while true; do
        echo -n "mcp> "
        read -r input
        
        if [ -z "$input" ]; then
            continue
        fi
        
        # Parse command and arguments
        set -- $input
        command="$1"
        shift
        
        case "$command" in
            "help"|"h")
                echo "Available commands:"
                echo "  test                     - Test connection to server"
                echo "  status                   - Get server status"
                echo "  health                   - Get health status"
                echo "  ingest <file_path>       - Ingest CSV file"
                echo "  query <text> [max] [threshold] - Query documents"
                echo "  verbose [on|off]         - Toggle verbose mode"
                echo "  help                     - Show this help"
                echo "  quit                     - Exit interactive mode"
                ;;
            "test"|"t")
                test_connection
                ;;
            "status"|"s")
                get_server_status
                ;;
            "health")
                get_health_status
                ;;
            "ingest"|"i")
                ingest_csv "$1"
                ;;
            "query"|"q")
                query_documents "$1" "$2" "$3"
                ;;
            "verbose"|"v")
                if [ "$1" = "on" ] || [ "$1" = "true" ]; then
                    VERBOSE=true
                    log_info "Verbose mode enabled"
                elif [ "$1" = "off" ] || [ "$1" = "false" ]; then
                    VERBOSE=false
                    log_info "Verbose mode disabled"
                else
                    log_info "Verbose mode: $VERBOSE"
                fi
                ;;
            "quit"|"exit"|"q")
                log_info "Exiting interactive mode"
                break
                ;;
            *)
                log_error "Unknown command: $command"
                echo "Type 'help' for available commands"
                ;;
        esac
        echo
    done
}

# Usage function
usage() {
    echo "RAG MCP Server - curl Client Test Script"
    echo
    echo "Usage: $0 [command] [arguments...]"
    echo
    echo "Commands:"
    echo "  test                           - Test connection to server"
    echo "  status                         - Get server status"
    echo "  health                         - Get health status"
    echo "  ingest <file_path>             - Ingest CSV file"
    echo "  query <text> [max] [threshold] - Query documents"
    echo "  interactive                    - Start interactive mode"
    echo "  help                           - Show this help"
    echo
    echo "Environment Variables:"
    echo "  MCP_SERVER_URL    - MCP server URL (default: http://localhost:8000/mcp/)"
    echo "  MCP_HEALTH_URL    - Health endpoint URL (default: http://localhost:8000/health)"
    echo "  VERBOSE           - Enable verbose output (default: false)"
    echo
    echo "Examples:"
    echo "  $0 test"
    echo "  $0 status"
    echo "  $0 ingest ./data/sample_products.csv"
    echo "  $0 query \"What products are available?\" 5 0.7"
    echo "  $0 interactive"
    echo
    echo "  MCP_SERVER_URL=http://remote-server:8000/mcp/ $0 test"
    echo "  VERBOSE=true $0 status"
}

# Main script logic
main() {
    # Check dependencies
    if ! command -v curl > /dev/null 2>&1; then
        log_error "curl is required but not installed"
        exit 1
    fi
    
    if ! command -v jq > /dev/null 2>&1; then
        log_error "jq is required but not installed"
        exit 1
    fi
    
    # Parse command line arguments
    case "${1:-test}" in
        "test"|"t")
            test_connection
            ;;
        "status"|"s")
            get_server_status
            ;;
        "health"|"h")
            get_health_status
            ;;
        "ingest"|"i")
            ingest_csv "$2"
            ;;
        "query"|"q")
            query_documents "$2" "$3" "$4"
            ;;
        "interactive"|"int")
            interactive_mode
            ;;
        "help"|"--help"|"-h")
            usage
            ;;
        *)
            log_error "Unknown command: $1"
            echo
            usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"