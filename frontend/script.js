// API Configuration
const API_BASE_URL = 'http://localhost:5000/api';

// Global State
let farms = [];
let selectedFarm = null;
let isDrawingMode = false;
let statusPollInterval = null;
let cameraStreamActive = false;
let resultsLoaded = false;

// DOM Elements
const elements = {
    // Connection
    connectionStatus: document.getElementById('connectionStatus'),
    connectionText: document.getElementById('connectionText'),
    
    // Farm Form
    farmName: document.getElementById('farmName'),
    farmLocation: document.getElementById('farmLocation'),
    minX: document.getElementById('minX'),
    minY: document.getElementById('minY'),
    maxX: document.getElementById('maxX'),
    maxY: document.getElementById('maxY'),
    
    // Buttons
    drawBtn: document.getElementById('drawBtn'),
    saveBtn: document.getElementById('saveBtn'),
    deployBtn: document.getElementById('deployBtn'),
    stallBtn: document.getElementById('stallBtn'),
    abortBtn: document.getElementById('abortBtn'),
    
    // Display Areas
    farmsList: document.getElementById('farmsList'),
    mapCanvas: document.getElementById('mapCanvas'),
    droneStatus: document.getElementById('droneStatus'),
    dronePosition: document.getElementById('dronePosition'),
    droneWaypoint: document.getElementById('droneWaypoint'),
    activeFarm: document.getElementById('activeFarm'),
    systemLog: document.getElementById('systemLog'),
    cameraStream: document.getElementById('cameraStream'),
    cameraPlaceholder: document.getElementById('cameraPlaceholder'),
    aiDetection: document.getElementById('aiDetection'),
    aiDetectionRow: document.getElementById('aiDetectionRow'),
    
    // Results
    resultsSection: document.getElementById('resultsSection'),
    resultsSummary: document.getElementById('resultsSummary'),
    heatmapImage: document.getElementById('heatmapImage'),
    detectionsTable: document.getElementById('detectionsTable'),
    exportBtn: document.getElementById('exportBtn'),
    clearResultsBtn: document.getElementById('clearResultsBtn')
};

// ============= INITIALIZATION =============

async function initialize() {
    logMessage('Initializing system...');
    
    // Check server connection
    await checkConnection();
    
    // Load existing farms
    await loadFarms();
    
    // Setup event listeners
    setupEventListeners();
    
    // Start polling drone status
    startStatusPolling();
    
    logMessage('System ready', 'success');
}

// ============= API FUNCTIONS =============

async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.message || 'API request failed');
        }
        
        return result;
    } catch (error) {
        console.error('API Error:', error);
        logMessage(`API Error: ${error.message}`, 'error');
        throw error;
    }
}

async function checkConnection() {
    try {
        await apiCall('/drone/status');
        elements.connectionStatus.classList.remove('disconnected');
        elements.connectionText.textContent = 'Connected';
        return true;
    } catch (error) {
        elements.connectionStatus.classList.add('disconnected');
        elements.connectionText.textContent = 'Disconnected';
        return false;
    }
}

async function loadFarms() {
    try {
        const result = await apiCall('/farms');
        farms = result.farms;
        updateFarmsList();
        logMessage(`Loaded ${farms.length} farms`);
    } catch (error) {
        logMessage('Failed to load farms', 'error');
    }
}

async function addFarm(farmData) {
    try {
        const result = await apiCall('/farms', 'POST', farmData);
        farms.push(result.farm);
        updateFarmsList();
        logMessage(`Added farm: ${result.farm.name}`, 'success');
        return result.farm;
    } catch (error) {
        logMessage('Failed to add farm', 'error');
        throw error;
    }
}

async function deleteFarm(farmId) {
    try {
        await apiCall(`/farms/${farmId}`, 'DELETE');
        farms = farms.filter(f => f.id !== farmId);
        if (selectedFarm && selectedFarm.id === farmId) {
            selectedFarm = null;
            elements.deployBtn.disabled = true;
        }
        updateFarmsList();
        logMessage('Farm deleted', 'success');
    } catch (error) {
        logMessage('Failed to delete farm', 'error');
    }
}

async function deployDrone() {
    if (!selectedFarm) {
        alert('Please select a farm first');
        return;
    }
    
    try {
        const result = await apiCall('/drone/deploy', 'POST', {
            farm_id: selectedFarm.id
        });
        logMessage(`Drone deployed to ${selectedFarm.name}`, 'success');
        updateControlButtons('flying');
        resultsLoaded = false;
    } catch (error) {
        logMessage('Failed to deploy drone', 'error');
    }
}

async function stallDrone() {
    try {
        const result = await apiCall('/drone/stall', 'POST');
        logMessage(result.message, 'warning');
    } catch (error) {
        logMessage('Failed to stall drone', 'error');
    }
}

async function abortDrone() {
    if (!confirm('Are you sure you want to abort the mission?')) {
        return;
    }
    
    try {
        const result = await apiCall('/drone/abort', 'POST');
        logMessage(result.message, 'warning');
    } catch (error) {
        logMessage('Failed to abort mission', 'error');
    }
}

async function pollDroneStatus() {
    try {
        const result = await apiCall('/drone/status');
        const status = result.status;
        
        // Update UI
        updateDroneStatus(status);
        
        // Update control buttons based on status
        if (status.is_running) {
            updateControlButtons(status.status);
            startCameraStream();
        } else {
            updateControlButtons('idle');
            stopCameraStream();
            
            // Load results if mission just completed
            if (!resultsLoaded && (status.status === 'completed' || status.status === 'aborted')) {
                resultsLoaded = true;
                await loadResults();
            }
        }
    } catch (error) {
        // Connection lost
        elements.connectionStatus.classList.add('disconnected');
        elements.connectionText.textContent = 'Connection Lost';
        stopCameraStream();
    }
}

// ============= RESULTS FUNCTIONS =============

async function loadResults() {
    try {
        logMessage('Loading mission results...', 'info');
        
        // Show results section
        elements.resultsSection.style.display = 'block';
        
        // Load summary
        const summaryResult = await apiCall('/results/summary');
        displaySummary(summaryResult.summary);
        
        // Load heatmap
        const heatmapResult = await apiCall('/results/heatmap');
        elements.heatmapImage.src = 'data:image/png;base64,' + heatmapResult.heatmap;
        
        // Load detections
        const detectionsResult = await apiCall('/results/detections');
        displayDetections(detectionsResult.detections);
        
        logMessage('Mission results loaded successfully', 'success');
    } catch (error) {
        logMessage('Failed to load results: ' + error.message, 'error');
    }
}

function displaySummary(summary) {
    let html = '<div class="summary-grid">';
    
    if (Object.keys(summary).length === 0) {
        html += '<p class="no-data">No detections recorded during this mission</p>';
    } else {
        for (const [disease, data] of Object.entries(summary)) {
            const diseaseColor = getDiseaseColor(disease);
            html += `
                <div class="summary-card" style="border-left-color: rgb(${diseaseColor.join(',')})">
                    <div class="disease-name">${disease}</div>
                    <div class="disease-count">${data.count} detected</div>
                    <div class="disease-confidence">Avg: ${data.avg_confidence}%</div>
                </div>
            `;
        }
    }
    
    html += '</div>';
    elements.resultsSummary.innerHTML = html;
}

function displayDetections(detections) {
    if (detections.length === 0) {
        elements.detectionsTable.innerHTML = '<p class="no-data">No detections recorded</p>';
        return;
    }
    
    let html = '<table class="detections-table-actual"><thead><tr>';
    html += '<th>Disease</th><th>Location (X, Y)</th><th>Confidence</th><th>Timestamp</th>';
    html += '</tr></thead><tbody>';
    
    for (const detection of detections) {
        const diseaseColor = getDiseaseColor(detection.disease);
        const timestamp = new Date(detection.timestamp).toLocaleTimeString();
        html += `<tr>
            <td><span class="disease-badge" style="background-color: rgb(${diseaseColor.join(',')})">
                ${detection.disease}
            </span></td>
            <td>(${detection.x.toFixed(2)}, ${detection.y.toFixed(2)})</td>
            <td>${(detection.confidence * 100).toFixed(1)}%</td>
            <td>${timestamp}</td>
        </tr>`;
    }
    
    html += '</tbody></table>';
    elements.detectionsTable.innerHTML = html;
}

function getDiseaseColor(disease) {
    const colors = {
        'HEALTHY': [0, 255, 0],
        'EARLY BLIGHT': [0, 165, 255],
        'LATE BLIGHT': [0, 0, 255],
        'LEAF MINER': [255, 0, 0],
        'LEAF MOLD': [255, 165, 0],
        'MOSAIC VIRUS': [128, 0, 128],
        'SEPTORIA': [255, 192, 203],
        'SPIDER MITES': [165, 42, 42],
        'YELLOW LEAF CURL': [0, 255, 255],
        'BACTERIAL SPOT': [139, 69, 19],
        'NO DETECTION': [128, 128, 128]
    };
    return colors[disease] || [128, 128, 128];
}

async function exportResults() {
    try {
        const result = await apiCall('/results/export');
        const dataStr = JSON.stringify(result, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `mission_results_${new Date().getTime()}.json`;
        link.click();
        logMessage('Results exported successfully', 'success');
    } catch (error) {
        logMessage('Failed to export results', 'error');
    }
}

async function clearResults() {
    if (!confirm('Clear all mission results?')) {
        return;
    }
    
    try {
        await apiCall('/results/clear', 'POST');
        elements.resultsSection.style.display = 'none';
        resultsLoaded = false;
        logMessage('Results cleared', 'success');
    } catch (error) {
        logMessage('Failed to clear results', 'error');
    }
}

// ============= CAMERA STREAMING =============

function startCameraStream() {
    if (!cameraStreamActive) {
        cameraStreamActive = true;
        elements.cameraStream.src = `${API_BASE_URL.replace('/api', '')}/api/camera/stream?t=${Date.now()}`;
        elements.cameraStream.classList.add('active');
        elements.cameraPlaceholder.classList.add('hidden');
        logMessage('Camera stream started', 'success');
    }
}

function stopCameraStream() {
    if (cameraStreamActive) {
        cameraStreamActive = false;
        elements.cameraStream.src = '';
        elements.cameraStream.classList.remove('active');
        elements.cameraPlaceholder.classList.remove('hidden');
    }
}

// ============= UI UPDATE FUNCTIONS =============

function updateFarmsList() {
    if (farms.length === 0) {
        elements.farmsList.innerHTML = '<p class="no-farms">No farms added yet</p>';
        return;
    }
    
    elements.farmsList.innerHTML = farms.map(farm => `
        <div class="farm-item ${selectedFarm && selectedFarm.id === farm.id ? 'selected' : ''}" 
             data-farm-id="${farm.id}">
            <div class="farm-name">${farm.name}</div>
            <div class="farm-location">📍 ${farm.location}</div>
            <div class="farm-actions">
                <button class="btn btn-primary btn-sm select-farm-btn" data-farm-id="${farm.id}">
                    Select
                </button>
                <button class="btn btn-danger btn-sm delete-farm-btn" data-farm-id="${farm.id}">
                    Delete
                </button>
            </div>
        </div>
    `).join('');
    
    // Add event listeners
    document.querySelectorAll('.select-farm-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const farmId = parseInt(e.target.dataset.farmId);
            selectFarm(farmId);
        });
    });
    
    document.querySelectorAll('.delete-farm-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const farmId = parseInt(e.target.dataset.farmId);
            deleteFarm(farmId);
        });
    });
}

function selectFarm(farmId) {
    selectedFarm = farms.find(f => f.id === farmId);
    updateFarmsList();
    elements.deployBtn.disabled = false;
    logMessage(`Selected farm: ${selectedFarm.name}`);
}

function updateDroneStatus(status) {
    // Update status text
    elements.droneStatus.textContent = status.status.toUpperCase();
    elements.droneStatus.style.color = getStatusColor(status.status);
    
    // Update position
    const pos = status.position;
    elements.dronePosition.textContent = `(${pos[0].toFixed(2)}, ${pos[1].toFixed(2)}, ${pos[2].toFixed(2)})`;
    
    // Update waypoint
    elements.droneWaypoint.textContent = `${status.current_waypoint} / ${status.total_waypoints}`;
    
    // Update active farm
    elements.activeFarm.textContent = status.current_farm ? status.current_farm.name : 'None';
    
    // Update AI detection if available
    if (status.ai_available && status.is_running) {
        elements.aiDetectionRow.style.display = 'flex';
        let aiText = status.ai_diagnosis || 'SCANNING...';
        if (status.ai_confidence && status.ai_confidence > 0) {
            aiText += ` (${status.ai_confidence}%)`;
        }
        elements.aiDetection.textContent = aiText;
        
        // Color based on health status
        if (status.ai_diagnosis === 'HEALTHY') {
            elements.aiDetection.style.color = '#48bb78';
        } else if (status.ai_diagnosis && status.ai_diagnosis !== 'SCANNING...' && status.ai_diagnosis !== 'NO DETECTION') {
            elements.aiDetection.style.color = '#f56565';
        } else {
            elements.aiDetection.style.color = '#a0aec0';
        }
    } else {
        elements.aiDetectionRow.style.display = 'none';
    }
}

function updateControlButtons(status) {
    switch(status) {
        case 'idle':
            elements.deployBtn.disabled = selectedFarm === null;
            elements.stallBtn.disabled = true;
            elements.abortBtn.disabled = true;
            break;
        case 'flying':
        case 'deploying':
            elements.deployBtn.disabled = true;
            elements.stallBtn.disabled = false;
            elements.abortBtn.disabled = false;
            elements.stallBtn.innerHTML = '<span class="btn-icon">⏸</span> STALL DRONE';
            break;
        case 'stalled':
            elements.deployBtn.disabled = true;
            elements.stallBtn.disabled = false;
            elements.abortBtn.disabled = false;
            elements.stallBtn.innerHTML = '<span class="btn-icon">▶</span> RESUME DRONE';
            break;
        case 'returning_home':
            elements.deployBtn.disabled = true;
            elements.stallBtn.disabled = true;
            elements.abortBtn.disabled = true;
            logMessage('Drone returning to home position...', 'warning');
            break;
        case 'completed':
        case 'aborted':
            elements.deployBtn.disabled = selectedFarm === null;
            elements.stallBtn.disabled = true;
            elements.abortBtn.disabled = true;
            logMessage(`Mission ${status}!`, status === 'completed' ? 'success' : 'warning');
            break;
    }
}

function getStatusColor(status) {
    const colors = {
        'idle': '#718096',
        'deploying': '#ed8936',
        'flying': '#48bb78',
        'stalled': '#ecc94b',
        'returning_home': '#f59e0b',
        'completed': '#4299e1',
        'aborted': '#f56565',
        'error': '#f56565'
    };
    return colors[status] || '#718096';
}

// ============= MAP DRAWING =============

function toggleDrawMode() {
    isDrawingMode = !isDrawingMode;
    const canvas = elements.mapCanvas;
    
    if (isDrawingMode) {
        canvas.classList.add('active');
        elements.drawBtn.textContent = 'CLEAR';
        drawBoundaries();
    } else {
        canvas.classList.remove('active');
        elements.drawBtn.textContent = 'DRAW';
        clearCanvas();
    }
}

function drawBoundaries() {
    const canvas = elements.mapCanvas;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    ctx.clearRect(0, 0, width, height);
    
    const minX = parseFloat(elements.minX.value);
    const minY = parseFloat(elements.minY.value);
    const maxX = parseFloat(elements.maxX.value);
    const maxY = parseFloat(elements.maxY.value);
    
    const rangeX = maxX - minX;
    const rangeY = maxY - minY;
    const scale = Math.min((width - 40) / rangeX, (height - 40) / rangeY);
    const offsetX = 20;
    const offsetY = 20;
    
    const toCanvasX = (x) => offsetX + (x - minX) * scale;
    const toCanvasY = (y) => height - (offsetY + (y - minY) * scale);
    
    // Draw grid
    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 1;
    for (let x = minX; x <= maxX; x += 0.5) {
        ctx.beginPath();
        ctx.moveTo(toCanvasX(x), toCanvasY(minY));
        ctx.lineTo(toCanvasX(x), toCanvasY(maxY));
        ctx.stroke();
    }
    for (let y = minY; y <= maxY; y += 0.5) {
        ctx.beginPath();
        ctx.moveTo(toCanvasX(minX), toCanvasY(y));
        ctx.lineTo(toCanvasX(maxX), toCanvasY(y));
        ctx.stroke();
    }
    
    // Draw boundary
    ctx.strokeStyle = '#48bb78';
    ctx.lineWidth = 3;
    ctx.strokeRect(
        toCanvasX(minX),
        toCanvasY(maxY),
        (maxX - minX) * scale,
        (maxY - minY) * scale
    );
    
    // Draw origin point
    ctx.fillStyle = '#667eea';
    ctx.beginPath();
    ctx.arc(toCanvasX(0), toCanvasY(0), 5, 0, Math.PI * 2);
    ctx.fill();
    
    ctx.fillStyle = '#2d3748';
    ctx.font = '12px sans-serif';
    ctx.fillText('(0,0)', toCanvasX(0) + 8, toCanvasY(0) - 8);
}

function clearCanvas() {
    const canvas = elements.mapCanvas;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

// ============= EVENT LISTENERS =============

function setupEventListeners() {
    // Draw button
    elements.drawBtn.addEventListener('click', toggleDrawMode);
    
    // Save button
    elements.saveBtn.addEventListener('click', async () => {
        const farmData = {
            name: elements.farmName.value || `Farm ${farms.length + 1}`,
            location: elements.farmLocation.value || 'Unknown',
            boundaries: {
                min_x: parseFloat(elements.minX.value),
                min_y: parseFloat(elements.minY.value),
                max_x: parseFloat(elements.maxX.value),
                max_y: parseFloat(elements.maxY.value)
            }
        };
        
        try {
            await addFarm(farmData);
            elements.farmName.value = '';
            elements.farmLocation.value = '';
            clearCanvas();
            isDrawingMode = false;
            elements.mapCanvas.classList.remove('active');
            elements.drawBtn.textContent = 'DRAW';
        } catch (error) {
            alert('Failed to add farm');
        }
    });
    
    // Boundary inputs
    [elements.minX, elements.minY, elements.maxX, elements.maxY].forEach(input => {
        input.addEventListener('input', () => {
            if (isDrawingMode) {
                drawBoundaries();
            }
        });
    });
    
    // Drone control buttons
    elements.deployBtn.addEventListener('click', deployDrone);
    elements.stallBtn.addEventListener('click', stallDrone);
    elements.abortBtn.addEventListener('click', abortDrone);
    
    // Results tabs
    document.querySelectorAll('.results-tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tabName = e.target.dataset.tab;
            switchResultsTab(tabName);
        });
    });
    
    // Export and clear buttons
    elements.exportBtn.addEventListener('click', exportResults);
    elements.clearResultsBtn.addEventListener('click', clearResults);
}

function switchResultsTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.results-tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.results-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    event.target.classList.add('active');
}

// ============= POLLING =============

function startStatusPolling() {
    statusPollInterval = setInterval(pollDroneStatus, 500);
}

function stopStatusPolling() {
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
    }
}

// ============= LOGGING =============

function logMessage(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    logEntry.textContent = `[${timestamp}] ${message}`;
    
    elements.systemLog.appendChild(logEntry);
    elements.systemLog.scrollTop = elements.systemLog.scrollHeight;
    
    while (elements.systemLog.children.length > 50) {
        elements.systemLog.removeChild(elements.systemLog.firstChild);
    }
}

// ============= START APPLICATION =============

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

window.addEventListener('beforeunload', () => {
    stopStatusPolling();
    stopCameraStream();
});