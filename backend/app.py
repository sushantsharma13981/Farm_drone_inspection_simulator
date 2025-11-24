from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
import threading
import queue
import time
import json
import os
import cv2
import base64
import numpy as np

# Import the integrated drone simulator
from drone_sweeper import run_drone_simulation_flask

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# ================= GLOBAL STATE =================

class DroneSimulatorState:
    def __init__(self):
        self.is_running = False
        self.is_paused = False
        self.drone_id = None
        self.current_position = [0, 0, 0]
        self.current_waypoint = 0
        self.total_waypoints = 0
        self.status = "idle"
        self.simulation_thread = None
        self.command_queue = queue.Queue()
        self.farms = []
        self.current_farm = None
        self.camera_frame = None
        self.camera_lock = threading.Lock()
        self.ai_diagnosis = "SCANNING..."
        self.ai_confidence = 0.0
        self.disease_map = None  # DiseaseDetectionMap object

sim_state = DroneSimulatorState()
farms_db = []

# ================= API ROUTES =================

@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/farms', methods=['GET'])
def get_farms():
    """Get all farms"""
    return jsonify({
        'success': True,
        'farms': farms_db
    })

@app.route('/api/farms', methods=['POST'])
def add_farm():
    """Add a new farm"""
    data = request.json
    
    farm = {
        'id': len(farms_db) + 1,
        'name': data.get('name', f'Farm {len(farms_db) + 1}'),
        'location': data.get('location', 'Unknown'),
        'boundaries': data.get('boundaries', {
            'min_x': -2,
            'min_y': -2,
            'max_x': 2,
            'max_y': 2
        }),
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    farms_db.append(farm)
    
    return jsonify({
        'success': True,
        'message': 'Farm added successfully',
        'farm': farm
    })

@app.route('/api/farms/<int:farm_id>', methods=['DELETE'])
def delete_farm(farm_id):
    """Delete a farm"""
    global farms_db
    farms_db = [f for f in farms_db if f['id'] != farm_id]
    
    return jsonify({
        'success': True,
        'message': 'Farm deleted successfully'
    })

@app.route('/api/drone/status', methods=['GET'])
def get_drone_status():
    """Get current drone status"""
    return jsonify({
        'success': True,
        'status': {
            'is_running': sim_state.is_running,
            'is_paused': sim_state.is_paused,
            'position': sim_state.current_position,
            'current_waypoint': sim_state.current_waypoint,
            'total_waypoints': sim_state.total_waypoints,
            'status': sim_state.status,
            'current_farm': sim_state.current_farm,
            'ai_diagnosis': sim_state.ai_diagnosis,
            'ai_confidence': sim_state.ai_confidence,
            'ai_available': True
        }
    })

@app.route('/api/drone/deploy', methods=['POST'])
def deploy_drone():
    """Deploy drone to start mission"""
    if sim_state.is_running:
        return jsonify({
            'success': False,
            'message': 'Drone is already deployed'
        }), 400
    
    data = request.json
    farm_id = data.get('farm_id')
    
    # Find farm
    farm = next((f for f in farms_db if f['id'] == farm_id), None)
    if not farm:
        return jsonify({
            'success': False,
            'message': 'Farm not found'
        }), 404
    
    sim_state.current_farm = farm
    sim_state.status = "deploying"
    
    # Start simulation in a separate thread
    sim_state.simulation_thread = threading.Thread(
        target=run_drone_simulation_flask,
        args=(farm, sim_state),
        daemon=True
    )
    sim_state.simulation_thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Drone deployed successfully',
        'farm': farm
    })

@app.route('/api/drone/stall', methods=['POST'])
def stall_drone():
    """Pause/resume the drone"""
    if not sim_state.is_running:
        return jsonify({
            'success': False,
            'message': 'No active drone mission'
        }), 400
    
    sim_state.is_paused = not sim_state.is_paused
    sim_state.status = "stalled" if sim_state.is_paused else "flying"
    
    return jsonify({
        'success': True,
        'message': f'Drone {"stalled" if sim_state.is_paused else "resumed"}',
        'is_paused': sim_state.is_paused
    })

@app.route('/api/drone/abort', methods=['POST'])
def abort_drone():
    """Abort the current mission"""
    if not sim_state.is_running:
        return jsonify({
            'success': False,
            'message': 'No active drone mission'
        }), 400
    
    sim_state.command_queue.put('abort')
    
    return jsonify({
        'success': True,
        'message': 'Mission abort initiated'
    })

@app.route('/api/camera/stream')
def camera_stream():
    """Stream camera feed as MJPEG"""
    def generate():
        while True:
            with sim_state.camera_lock:
                if sim_state.camera_frame is not None:
                    _, buffer = cv2.imencode('.jpg', sim_state.camera_frame)
                    frame = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.033)  # ~30 FPS
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/camera/frame')
def camera_frame():
    """Get single camera frame as base64"""
    with sim_state.camera_lock:
        if sim_state.camera_frame is not None:
            _, buffer = cv2.imencode('.jpg', sim_state.camera_frame)
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            return jsonify({
                'success': True,
                'frame': img_base64
            })
    
    return jsonify({
        'success': False,
        'message': 'No camera frame available'
    })

# ================= RESULTS API =================

@app.route('/api/results/summary', methods=['GET'])
def get_results_summary():
    """Get disease detection summary"""
    if sim_state.disease_map is None:
        return jsonify({
            'success': False,
            'message': 'No mission data available'
        }), 404
    
    summary = sim_state.disease_map.get_summary()
    
    return jsonify({
        'success': True,
        'summary': summary,
        'total_detections': len(sim_state.disease_map.detections)
    })

@app.route('/api/results/detections', methods=['GET'])
def get_all_detections():
    """Get all individual detections"""
    if sim_state.disease_map is None:
        return jsonify({
            'success': False,
            'message': 'No mission data available'
        }), 404
    
    detections = sim_state.disease_map.get_all_detections()
    
    return jsonify({
        'success': True,
        'detections': detections
    })

@app.route('/api/results/heatmap', methods=['GET'])
def get_heatmap():
    """Get disease heatmap as image"""
    if sim_state.disease_map is None:
        return jsonify({
            'success': False,
            'message': 'No mission data available'
        }), 404
    
    heatmap = sim_state.disease_map.create_heatmap_image(600, 600)
    _, buffer = cv2.imencode('.png', heatmap)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    
    return jsonify({
        'success': True,
        'heatmap': img_base64
    })

@app.route('/api/results/export', methods=['GET'])
def export_results():
    """Export results as JSON"""
    if sim_state.disease_map is None:
        return jsonify({
            'success': False,
            'message': 'No mission data available'
        }), 404
    
    summary = sim_state.disease_map.get_summary()
    detections = sim_state.disease_map.get_all_detections()
    
    report = {
        'mission_info': {
            'farm': sim_state.current_farm['name'] if sim_state.current_farm else 'Unknown',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': sim_state.status
        },
        'summary': summary,
        'total_detections': len(detections),
        'detections': detections
    }
    
    return jsonify(report)

@app.route('/api/results/clear', methods=['POST'])
def clear_results():
    """Clear all mission results"""
    sim_state.disease_map = None
    
    return jsonify({
        'success': True,
        'message': 'Results cleared'
    })

# ================= MAIN =================

if __name__ == '__main__':
    # Add default test farms
    farms_db.append({
        'id': 1,
        'name': 'North Field Farm',
        'location': 'Sector A1',
        'boundaries': {'min_x': -3, 'min_y': -3, 'max_x': 3, 'max_y': 3},
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
    })
    
    print("🚀 Farm Drone Inspection Server Starting...")
    print("🔗 Server running on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)