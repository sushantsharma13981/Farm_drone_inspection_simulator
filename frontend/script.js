// API Configuration
const API_BASE_URL = 'http://localhost:5000/api';

// Global State
let farms = [];
let selectedFarm = null;
let isDrawingMode = false;
let statusPollInterval = null;

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
    totalFarms: document.getElementById('totalFarms'),
    activeMissions: document.getElementById('activeMissions'),
    systemLog: document.getElementById('systemLog')
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
        updateDatabaseStats();
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
        updateDatabaseStats();
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
        updateDatabaseStats();
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
        } else {
            updateControlButtons('idle');
        }
    } catch (error) {
        // Connection lost
        elements.connectionStatus.classList.add('disconnected');
        elements.connectionText.textContent = 'Connection Lost';
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
    
    // Update active missions count
    elements.activeMissions.textContent = status.is_running ? '1' : '0';
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

function updateDatabaseStats() {
    elements.totalFarms.textContent = farms.length;
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
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Get boundary values
    const minX = parseFloat(elements.minX.value);
    const minY = parseFloat(elements.minY.value);
    const maxX = parseFloat(elements.maxX.value);
    const maxY = parseFloat(elements.maxY.value);
    
    // Calculate scale and offset
    const rangeX = maxX - minX;
    const rangeY = maxY - minY;
    const scale = Math.min((width - 40) / rangeX, (height - 40) / rangeY);
    const offsetX = 20;
    const offsetY = 20;
    
    // Transform coordinates to canvas space
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
    
    // Label origin
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
            // Clear form
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
    
    // Boundary inputs - redraw on change
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
}

// ============= POLLING =============

function startStatusPolling() {
    // Poll every 500ms
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
    
    // Keep only last 50 entries
    while (elements.systemLog.children.length > 50) {
        elements.systemLog.removeChild(elements.systemLog.firstChild);
    }
}

// ============= START APPLICATION =============

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    stopStatusPolling();
});