// API Base URL
const API_BASE = '/api';

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadUploadedFiles();
    
    // Set up event listeners
    document.getElementById('uploadForm').addEventListener('submit', handleUpload);
    document.getElementById('queryForm').addEventListener('submit', handleQuery);
    document.getElementById('refreshFilesBtn').addEventListener('click', loadUploadedFiles);
    
    // Check health every 30 seconds
    setInterval(checkHealth, 30000);
});

// Check server health
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();
        
        const statusEl = document.getElementById('healthStatus');
        const isHealthy = data.status === 'healthy';
        
        statusEl.innerHTML = `
            <strong>Status:</strong> 
            <span style="color: ${isHealthy ? '#28a745' : '#ffc107'}">
                ${isHealthy ? '✓ Healthy' : '⚠ Degraded'}
            </span>
            ${!isHealthy ? `<br><small>${JSON.stringify(data.components)}</small>` : ''}
        `;
    } catch (error) {
        document.getElementById('healthStatus').innerHTML = `
            <strong>Status:</strong> <span style="color: #dc3545">✗ Offline</span>
        `;
    }
}

// Handle CSV upload
async function handleUpload(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('csvFile');
    const file = fileInput.files[0];
    
    if (!file) {
        showResult('uploadResult', 'Please select a file', 'error');
        return;
    }
    
    // Show loading state
    setButtonLoading('uploadBtnText', 'uploadSpinner', true);
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(`${API_BASE}/upload-csv`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showUploadSuccess(data);
            fileInput.value = ''; // Clear file input
            loadUploadedFiles(); // Refresh file list
        } else {
            showResult('uploadResult', `Error: ${data.detail}`, 'error');
        }
    } catch (error) {
        showResult('uploadResult', `Upload failed: ${error.message}`, 'error');
    } finally {
        setButtonLoading('uploadBtnText', 'uploadSpinner', false);
    }
}

// Show upload success with stats
function showUploadSuccess(data) {
    const result = data.ingestion_result;
    const resultEl = document.getElementById('uploadResult');
    
    let html = `
        <div class="result success">
            <h3>✓ Upload Successful</h3>
            <p>${data.message}</p>
    `;
    
    if (result) {
        html += `
            <div class="ingestion-stats">
                <div class="stat-item">
                    <div class="stat-value">${result.documents_processed}</div>
                    <div class="stat-label">Documents</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${result.chunks_created}</div>
                    <div class="stat-label">Chunks</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${result.embeddings_generated}</div>
                    <div class="stat-label">Embeddings</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${result.processing_time_seconds?.toFixed(2) || 'N/A'}s</div>
                    <div class="stat-label">Time</div>
                </div>
            </div>
        `;
        
        if (result.errors && result.errors.length > 0) {
            html += `
                <div style="margin-top: 15px; padding: 10px; background: #fff3cd; border-radius: 4px;">
                    <strong>Warnings:</strong>
                    <ul style="margin: 5px 0 0 20px;">
                        ${result.errors.map(err => `<li>${err}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
    }
    
    html += '</div>';
    resultEl.innerHTML = html;
}

// Handle document query
async function handleQuery(e) {
    e.preventDefault();
    
    const query = document.getElementById('queryInput').value;
    const maxResults = parseInt(document.getElementById('maxResults').value);
    const scoreThreshold = document.getElementById('scoreThreshold').value;
    
    // Show loading state
    setButtonLoading('queryBtnText', 'querySpinner', true);
    
    const requestBody = {
        query: query,
        max_results: maxResults
    };
    
    if (scoreThreshold) {
        requestBody.score_threshold = parseFloat(scoreThreshold);
    }
    
    try {
        const response = await fetch(`${API_BASE}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            displayQueryResults(data);
        } else {
            showResult('queryResults', `Error: ${data.detail}`, 'error');
        }
    } catch (error) {
        showResult('queryResults', `Query failed: ${error.message}`, 'error');
    } finally {
        setButtonLoading('queryBtnText', 'querySpinner', false);
    }
}

// Display query results
function displayQueryResults(results) {
    const container = document.getElementById('queryResults');
    
    if (!results || results.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No results found. Try a different query or upload more documents.</p>
            </div>
        `;
        return;
    }
    
    let html = `<h3>Found ${results.length} results:</h3>`;
    
    results.forEach((result, index) => {
        const score = (result.similarity_score * 100).toFixed(1);
        const content = result.content.substring(0, 300) + (result.content.length > 300 ? '...' : '');
        
        html += `
            <div class="result-item">
                <div class="result-header">
                    <strong>Result ${index + 1}</strong>
                    <span class="similarity-score">${score}% match</span>
                </div>
                <div class="result-content">${escapeHtml(content)}</div>
                <div class="result-metadata">
                    <strong>Source:</strong> ${escapeHtml(result.metadata.source_file || 'Unknown')}<br>
                    <strong>Row:</strong> ${result.metadata.row_number || 'N/A'}<br>
                    <strong>Chunk:</strong> ${result.chunk_id.substring(0, 8)}...
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// Load uploaded files
async function loadUploadedFiles() {
    try {
        const response = await fetch(`${API_BASE}/uploaded-files`);
        const data = await response.json();
        
        const container = document.getElementById('filesList');
        
        if (!data.files || data.files.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No files uploaded yet.</p>
                </div>
            `;
            return;
        }
        
        let html = '';
        data.files.forEach(file => {
            const sizeKB = (file.size_bytes / 1024).toFixed(2);
            const date = new Date(file.uploaded_at * 1000).toLocaleString();
            
            html += `
                <div class="file-item">
                    <div>
                        <div class="file-name">📄 ${escapeHtml(file.filename)}</div>
                        <div class="file-info">${sizeKB} KB • Uploaded: ${date}</div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    } catch (error) {
        console.error('Failed to load files:', error);
    }
}

// Utility functions
function showResult(elementId, message, type) {
    const el = document.getElementById(elementId);
    el.className = `result ${type}`;
    el.textContent = message;
}

function setButtonLoading(textId, spinnerId, isLoading) {
    const textEl = document.getElementById(textId);
    const spinnerEl = document.getElementById(spinnerId);
    const button = textEl.closest('button');
    
    if (isLoading) {
        textEl.style.display = 'none';
        spinnerEl.style.display = 'inline-block';
        button.disabled = true;
    } else {
        textEl.style.display = 'inline';
        spinnerEl.style.display = 'none';
        button.disabled = false;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
