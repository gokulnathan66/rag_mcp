#!/usr/bin/env node

/**
 * Simple Node.js MCP Client for RAG MCP Server
 * 
 * This script demonstrates how to connect to and interact with the RAG MCP Server
 * using HTTP transport from Node.js applications.
 */

const axios = require('axios');
const readline = require('readline');

class RAGMCPClient {
    /**
     * Initialize the MCP client.
     * 
     * @param {string} baseUrl - Base URL of the RAG MCP Server
     */
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.mcpUrl = `${this.baseUrl}/mcp/`;
        this.healthUrl = `${this.baseUrl}/health`;
        this.requestId = 1;
        this.timeout = 30000; // 30 seconds
    }

    /**
     * Make an MCP JSON-RPC request.
     * 
     * @param {string} method - MCP method name
     * @param {Object} params - Method parameters
     * @returns {Promise<Object>} JSON-RPC response
     */
    async makeRequest(method, params) {
        const payload = {
            jsonrpc: '2.0',
            id: this.requestId++,
            method: method,
            params: params
        };

        try {
            const response = await axios.post(this.mcpUrl, payload, {
                headers: { 'Content-Type': 'application/json' },
                timeout: this.timeout
            });

            const result = response.data;

            // Check for JSON-RPC errors
            if (result.error) {
                const error = result.error;
                throw new Error(`MCP Error ${error.code || 'UNKNOWN'}: ${error.message || 'Unknown error'}`);
            }

            return result;

        } catch (error) {
            if (error.response) {
                throw new Error(`HTTP ${error.response.status}: ${error.response.statusText}`);
            } else if (error.request) {
                throw new Error(`Network error: ${error.message}`);
            } else {
                throw new Error(`Request error: ${error.message}`);
            }
        }
    }

    /**
     * Get server status.
     * 
     * @returns {Promise<Object>} Server status information
     */
    async getServerStatus() {
        const response = await this.makeRequest('tools/call', {
            name: 'get_server_status',
            arguments: {}
        });
        return response.result || {};
    }

    /**
     * Ingest a CSV file.
     * 
     * @param {string} filePath - Path to the CSV file
     * @returns {Promise<Object>} Ingestion result
     */
    async ingestCsv(filePath) {
        const response = await this.makeRequest('tools/call', {
            name: 'ingest_csv',
            arguments: { file_path: filePath }
        });
        return response.result || {};
    }

    /**
     * Query documents.
     * 
     * @param {string} query - Natural language query
     * @param {number} maxResults - Maximum number of results
     * @param {number|null} scoreThreshold - Minimum similarity score
     * @returns {Promise<Array>} Query results
     */
    async queryDocuments(query, maxResults = 10, scoreThreshold = null) {
        const args = { query, max_results: maxResults };
        if (scoreThreshold !== null) {
            args.score_threshold = scoreThreshold;
        }

        const response = await this.makeRequest('tools/call', {
            name: 'query_documents',
            arguments: args
        });
        return response.result || [];
    }

    /**
     * Get health status via HTTP endpoint.
     * 
     * @returns {Promise<Object>} Health status information
     */
    async getHealth() {
        try {
            const response = await axios.get(this.healthUrl, { timeout: 10000 });
            return response.data;
        } catch (error) {
            if (error.response) {
                throw new Error(`Health check failed: HTTP ${error.response.status}`);
            } else {
                throw new Error(`Health check failed: ${error.message}`);
            }
        }
    }

    /**
     * Test connection to the server.
     * 
     * @returns {Promise<boolean>} True if connection successful
     */
    async testConnection() {
        try {
            // Test health endpoint
            const health = await this.getHealth();
            console.log(`✓ Health check passed: ${health.status}`);

            // Test MCP endpoint
            const status = await this.getServerStatus();
            console.log(`✓ MCP connection successful: ${status.server_name} v${status.version}`);
            console.log(`  Status: ${status.status}`);
            console.log(`  Components:`, status.components);

            return true;

        } catch (error) {
            console.error(`✗ Connection test failed: ${error.message}`);
            return false;
        }
    }
}

/**
 * Interactive CLI interface
 */
class InteractiveCLI {
    constructor(client) {
        this.client = client;
        this.rl = readline.createInterface({
            input: process.stdin,
            output: process.stdout,
            prompt: 'mcp> '
        });
    }

    /**
     * Start interactive mode
     */
    async start() {
        console.log('RAG MCP Server - Interactive Node.js Client');
        console.log('Type "help" for available commands, "quit" to exit');
        console.log();

        this.rl.prompt();

        this.rl.on('line', async (input) => {
            const trimmed = input.trim();
            if (!trimmed) {
                this.rl.prompt();
                return;
            }

            const [command, ...args] = trimmed.split(' ');

            try {
                await this.handleCommand(command.toLowerCase(), args);
            } catch (error) {
                console.error(`Error: ${error.message}`);
            }

            console.log();
            this.rl.prompt();
        });

        this.rl.on('close', () => {
            console.log('Goodbye!');
            process.exit(0);
        });
    }

    /**
     * Handle CLI commands
     */
    async handleCommand(command, args) {
        switch (command) {
            case 'help':
            case 'h':
                this.showHelp();
                break;

            case 'test':
            case 't':
                await this.client.testConnection();
                break;

            case 'status':
            case 's':
                const status = await this.client.getServerStatus();
                console.log(JSON.stringify(status, null, 2));
                break;

            case 'health':
                const health = await this.client.getHealth();
                console.log(JSON.stringify(health, null, 2));
                break;

            case 'ingest':
            case 'i':
                if (args.length === 0) {
                    console.log('Usage: ingest <file_path>');
                    break;
                }
                const filePath = args.join(' ');
                console.log(`Ingesting CSV file: ${filePath}`);
                const ingestResult = await this.client.ingestCsv(filePath);
                console.log(JSON.stringify(ingestResult, null, 2));
                break;

            case 'query':
            case 'q':
                if (args.length === 0) {
                    console.log('Usage: query <query_text> [max_results] [score_threshold]');
                    break;
                }
                
                const queryText = args.join(' ').replace(/\s+\d+(\.\d+)?$/, '').replace(/\s+\d+$/, '');
                const maxResults = parseInt(args[args.length - 2]) || 10;
                const scoreThreshold = parseFloat(args[args.length - 1]) || null;
                
                console.log(`Querying documents: ${queryText}`);
                const queryResults = await this.client.queryDocuments(queryText, maxResults, scoreThreshold);
                console.log(JSON.stringify(queryResults, null, 2));
                break;

            case 'quit':
            case 'exit':
            case 'q':
                this.rl.close();
                break;

            default:
                console.log(`Unknown command: ${command}`);
                console.log('Type "help" for available commands');
        }
    }

    /**
     * Show help information
     */
    showHelp() {
        console.log('Available commands:');
        console.log('  test                              - Test connection to server');
        console.log('  status                            - Get server status');
        console.log('  health                            - Get health status');
        console.log('  ingest <file_path>                - Ingest CSV file');
        console.log('  query <text> [max] [threshold]    - Query documents');
        console.log('  help                              - Show this help');
        console.log('  quit                              - Exit');
    }
}

/**
 * Command-line interface for non-interactive usage
 */
async function runCommand(client, command, args) {
    switch (command) {
        case 'test':
            const success = await client.testConnection();
            process.exit(success ? 0 : 1);
            break;

        case 'status':
            const status = await client.getServerStatus();
            console.log(JSON.stringify(status, null, 2));
            break;

        case 'health':
            const health = await client.getHealth();
            console.log(JSON.stringify(health, null, 2));
            break;

        case 'ingest':
            if (args.length === 0) {
                console.error('Usage: node simple-client.js ingest <file_path>');
                process.exit(1);
            }
            const filePath = args.join(' ');
            console.log(`Ingesting CSV file: ${filePath}`);
            const ingestResult = await client.ingestCsv(filePath);
            console.log(JSON.stringify(ingestResult, null, 2));
            break;

        case 'query':
            if (args.length === 0) {
                console.error('Usage: node simple-client.js query <query_text> [max_results] [score_threshold]');
                process.exit(1);
            }
            
            // Parse arguments - last two might be numbers
            let queryText = args.join(' ');
            let maxResults = 10;
            let scoreThreshold = null;
            
            // Check if last argument is a number (score threshold)
            const lastArg = args[args.length - 1];
            if (!isNaN(parseFloat(lastArg)) && isFinite(lastArg)) {
                scoreThreshold = parseFloat(lastArg);
                args.pop();
                
                // Check if second-to-last argument is also a number (max results)
                const secondLastArg = args[args.length - 1];
                if (!isNaN(parseInt(secondLastArg)) && isFinite(secondLastArg)) {
                    maxResults = parseInt(secondLastArg);
                    args.pop();
                }
                
                queryText = args.join(' ');
            } else {
                // Check if last argument is an integer (max results)
                if (!isNaN(parseInt(lastArg)) && isFinite(lastArg)) {
                    maxResults = parseInt(lastArg);
                    args.pop();
                    queryText = args.join(' ');
                }
            }
            
            console.log(`Querying documents: ${queryText}`);
            if (maxResults !== 10) console.log(`Max results: ${maxResults}`);
            if (scoreThreshold !== null) console.log(`Score threshold: ${scoreThreshold}`);
            
            const queryResults = await client.queryDocuments(queryText, maxResults, scoreThreshold);
            console.log(JSON.stringify(queryResults, null, 2));
            break;

        case 'interactive':
            const cli = new InteractiveCLI(client);
            await cli.start();
            break;

        default:
            console.error(`Unknown command: ${command}`);
            showUsage();
            process.exit(1);
    }
}

/**
 * Show usage information
 */
function showUsage() {
    console.log('RAG MCP Server - Node.js Client');
    console.log();
    console.log('Usage: node simple-client.js [server_url] [command] [arguments...]');
    console.log();
    console.log('Commands:');
    console.log('  test                              - Test connection to server');
    console.log('  status                            - Get server status');
    console.log('  health                            - Get health status');
    console.log('  ingest <file_path>                - Ingest CSV file');
    console.log('  query <text> [max] [threshold]    - Query documents');
    console.log('  interactive                       - Start interactive mode');
    console.log();
    console.log('Examples:');
    console.log('  node simple-client.js test');
    console.log('  node simple-client.js status');
    console.log('  node simple-client.js ingest ./data/sample_products.csv');
    console.log('  node simple-client.js query "What products are available?" 5 0.7');
    console.log('  node simple-client.js interactive');
    console.log('  node simple-client.js http://remote-server:8000 test');
}

/**
 * Main function
 */
async function main() {
    const args = process.argv.slice(2);
    
    // Check if axios is available
    try {
        require('axios');
    } catch (error) {
        console.error('Error: axios is required but not installed');
        console.error('Install it with: npm install axios');
        process.exit(1);
    }
    
    // Parse arguments
    let serverUrl = 'http://localhost:8000';
    let command = 'interactive';
    let commandArgs = [];
    
    if (args.length === 0) {
        // Default to interactive mode
        command = 'interactive';
    } else if (args[0].startsWith('http://') || args[0].startsWith('https://')) {
        // First argument is server URL
        serverUrl = args[0];
        command = args[1] || 'interactive';
        commandArgs = args.slice(2);
    } else if (args[0] === 'help' || args[0] === '--help' || args[0] === '-h') {
        showUsage();
        return;
    } else {
        // First argument is command
        command = args[0];
        commandArgs = args.slice(1);
    }
    
    console.log(`Connecting to RAG MCP Server at: ${serverUrl}`);
    
    // Create client
    const client = new RAGMCPClient(serverUrl);
    
    try {
        await runCommand(client, command, commandArgs);
    } catch (error) {
        console.error(`Error: ${error.message}`);
        process.exit(1);
    }
}

// Run main function if this script is executed directly
if (require.main === module) {
    main().catch(error => {
        console.error(`Fatal error: ${error.message}`);
        process.exit(1);
    });
}

module.exports = RAGMCPClient;