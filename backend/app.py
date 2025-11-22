from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import threading
import queue
import time
import json
import numpy as np
import pybullet as p
import pybullet_data
import os
import random
import math

# Import your existing drone modules
from DSLPIDControl import DSLPIDControl
from enums import DroneModel

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# Global state management
class DroneSimulatorState:
    def __init__(self):
        self.is_running = False
        self.is_paused = False
        self.drone_id = None
        self.current_position = [0, 0, 0]
        self.current_waypoint = 0
        self.total_waypoints = 0
        self.status = "idle"  # idle, deploying, flying, stalled, completed, aborted
        self.simulation_thread = None
        self.command_queue = queue.Queue()
        self.farms = []
        self.current_farm = None
        
sim_state = DroneSimulatorState()

# Database simulation (in-memory for now)
farms_db = []

# ============= API ROUTES =============

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
            'current_farm': sim_state.current_farm
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
        target=run_drone_simulation,
        args=(farm,),
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
    """Pause/stall the drone"""
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

# ============= HELPER FUNCTIONS FROM DRONE_SWEEPER =============

def setup_simulation(drone_urdf_path):
    """Setup PyBullet simulation"""
    print("Connecting to PyBullet...")
    if p.isConnected():
        p.disconnect()
    p.connect(p.GUI)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    
    p.setGravity(0, 0, -9.81)
    p.setPhysicsEngineParameter(fixedTimeStep=1.0/240.0)
    planeId = p.loadURDF("plane.urdf")
    
    print(f"Loading drone from {drone_urdf_path}...")
    start_pos = [0, 0, 0.1]
    start_orn = p.getQuaternionFromEuler([0, 0, 0])
    droneId = p.loadURDF(drone_urdf_path, start_pos, start_orn)
    
    return droneId, planeId

def draw_field_boundaries(min_corner, max_corner, z=0.01):
    """Draw field boundaries in PyBullet"""
    x_min, y_min = min_corner
    x_max, y_max = max_corner
    c0, c1 = [x_min, y_min, z], [x_max, y_min, z]
    c2, c3 = [x_max, y_max, z], [x_min, y_max, z]
    color = [0, 1, 0]
    p.addUserDebugLine(c0, c1, color, lineWidth=3)
    p.addUserDebugLine(c1, c2, color, lineWidth=3)
    p.addUserDebugLine(c2, c3, color, lineWidth=3)
    p.addUserDebugLine(c3, c0, color, lineWidth=3)

def setup_field(field_min_corner, field_max_corner, num_bad_crops=10):
    """Setup field with bad crops"""
    print(f"Planting {num_bad_crops} bad crops...")
    for _ in range(num_bad_crops):
        x = random.uniform(field_min_corner[0], field_max_corner[0])
        y = random.uniform(field_min_corner[1], field_max_corner[1])
        pos = [x, y, 0.05]
        vs_id = p.createVisualShape(p.GEOM_SPHERE, radius=0.05, rgbaColor=[1, 0, 0, 1])
        p.createMultiBody(basePosition=pos, baseCollisionShapeIndex=-1, baseVisualShapeIndex=vs_id)

def get_sweep_waypoints(field_min, field_max, z_hover, sweep_step=0.5):
    """Generate sweep waypoints for the field"""
    waypoints = []
    # 1. Takeoff (Straight up)
    waypoints.append(np.array([0, 0, z_hover]))
    
    # 2. Move to Start Corner
    waypoints.append(np.array([field_min[0], field_min[1], z_hover]))

    x_min, y_min = field_min
    x_max, y_max = field_max
    
    current_y = y_min
    going_right = True
    
    while current_y <= y_max:
        x_start = x_min if going_right else x_max
        x_end   = x_max if going_right else x_min
        
        # Row endpoints
        waypoints.append(np.array([x_start, current_y, z_hover]))
        waypoints.append(np.array([x_end,   current_y, z_hover]))
        
        # Move to next row
        current_y += sweep_step
        if current_y <= y_max + sweep_step:
            waypoints.append(np.array([x_end, current_y, z_hover]))
            
        going_right = not going_right

    # 3. Return Home and LAND
    waypoints.append(np.array([0, 0, z_hover])) # Return to home (High)
    waypoints.append(np.array([0, 0, 0.05]))    # LAND (Low)
    
    return waypoints

# ============= DRONE SIMULATION =============

def run_drone_simulation(farm):
    """Run the drone simulation with the given farm parameters"""
    sim_state.is_running = True
    sim_state.status = "flying"
    sim_state.current_waypoint = 0
    
    try:
        # Extract farm boundaries
        bounds = farm['boundaries']
        field_min = [bounds['min_x'], bounds['min_y']]
        field_max = [bounds['max_x'], bounds['max_y']]
        
        # Setup simulation
        drone_id, _ = setup_simulation("cf2p.urdf")
        sim_state.drone_id = drone_id
        draw_field_boundaries(field_min, field_max)
        setup_field(field_min, field_max, num_bad_crops=10)
        
        # Generate waypoints
        HOVER_ALTITUDE = 1.0
        SWEEP_STEP = 0.75
        CRUISE_SPEED = 0.5
        WAIT_TIME_AT_CORNER = 1.5
        CTRL_TIMESTEP = 1.0 / 48.0
        SIM_HZ = 240.0
        CTRL_HZ = 48.0
        SIM_STEPS = int(SIM_HZ / CTRL_HZ)
        
        waypoints = get_sweep_waypoints(field_min, field_max, HOVER_ALTITUDE, SWEEP_STEP)
        sim_state.total_waypoints = len(waypoints)
        
        ctrl = DSLPIDControl(drone_model=DroneModel.CF2P)
        
        # Trajectory state
        current_wp_idx = 0
        virtual_pos = np.array([0.0, 0.0, 0.1])
        target_vel = np.zeros(3)
        wait_timer = 0.0
        is_waiting = False
        
        print(f"[SERVER] Starting mission for {farm['name']}")
        
        abort_initiated = False
        return_home_waypoints = None
        
        while current_wp_idx < len(waypoints):
            # Check for abort command
            try:
                cmd = sim_state.command_queue.get_nowait()
                if cmd == 'abort' and not abort_initiated:
                    print("[SERVER] Mission aborted by user - Returning to home")
                    sim_state.status = "returning_home"
                    abort_initiated = True
                    
                    # Get current position
                    cur_pos_abort, _ = p.getBasePositionAndOrientation(drone_id)
                    
                    # Create return home waypoints: current position -> home at hover altitude -> land
                    return_home_waypoints = [
                        np.array([cur_pos_abort[0], cur_pos_abort[1], HOVER_ALTITUDE]),
                        np.array([0, 0, HOVER_ALTITUDE]),
                        np.array([0, 0, 0.05])
                    ]
                    
                    # Reset waypoint tracking for return journey
                    waypoints = return_home_waypoints
                    current_wp_idx = 0
                    virtual_pos = np.array([cur_pos_abort[0], cur_pos_abort[1], cur_pos_abort[2]])
                    is_waiting = False
                    wait_timer = 0.0
                    
                    print(f"[SERVER] Return home path set: {len(return_home_waypoints)} waypoints")
            except queue.Empty:
                pass
            
            # Handle pause/stall
            while sim_state.is_paused:
                time.sleep(0.1)
                continue
            
            # Get drone state
            cur_pos, cur_quat = p.getBasePositionAndOrientation(drone_id)
            cur_vel, cur_ang_vel = p.getBaseVelocity(drone_id)
            
            # Update global state
            sim_state.current_position = list(cur_pos)
            sim_state.current_waypoint = current_wp_idx
            
            # Update virtual target
            goal = waypoints[current_wp_idx]
            vector_to_goal = goal - virtual_pos
            dist_to_goal = np.linalg.norm(vector_to_goal)
            
            if is_waiting:
                target_vel = np.zeros(3)
                wait_timer += CTRL_TIMESTEP
                drone_dist = np.linalg.norm(np.array(cur_pos) - virtual_pos)
                
                if wait_timer >= WAIT_TIME_AT_CORNER and drone_dist < 0.2:
                    is_waiting = False
                    current_wp_idx += 1
                    wait_timer = 0.0
            
            elif dist_to_goal < 0.05:
                is_waiting = True
                target_vel = np.zeros(3)
                virtual_pos = goal
            
            else:
                direction = vector_to_goal / dist_to_goal
                target_vel = direction * CRUISE_SPEED
                virtual_pos += target_vel * CTRL_TIMESTEP
            
            # Controller
            rpm, _, _ = ctrl.computeControl(
                control_timestep=CTRL_TIMESTEP,
                cur_pos=np.array(cur_pos),
                cur_quat=np.array(cur_quat),
                cur_vel=np.array(cur_vel),
                cur_ang_vel=np.array(cur_ang_vel),
                target_pos=virtual_pos,
                target_vel=target_vel
            )
            
            # Physics
            forces = ctrl.KF * (rpm**2)
            for _ in range(SIM_STEPS):
                p.applyExternalForce(drone_id, 0, [0, 0, forces[0]], [0, 0, 0], p.LINK_FRAME)
                p.applyExternalForce(drone_id, 1, [0, 0, forces[1]], [0, 0, 0], p.LINK_FRAME)
                p.applyExternalForce(drone_id, 2, [0, 0, forces[2]], [0, 0, 0], p.LINK_FRAME)
                p.applyExternalForce(drone_id, 3, [0, 0, forces[3]], [0, 0, 0], p.LINK_FRAME)
                p.stepSimulation()
                time.sleep(1.0 / SIM_HZ)
        
        if abort_initiated:
            sim_state.status = "aborted"
            print(f"[SERVER] Drone returned to home after abort")
        elif sim_state.status != "aborted":
            sim_state.status = "completed"
            print(f"[SERVER] Mission completed for {farm['name']}")
        
        # Let physics settle
        for _ in range(100):
            p.stepSimulation()
            time.sleep(1.0 / SIM_HZ)
    
    except Exception as e:
        print(f"[SERVER] Simulation error: {e}")
        sim_state.status = "error"
    
    finally:
        sim_state.is_running = False
        sim_state.is_paused = False
        if p.isConnected():
            p.disconnect()

if __name__ == '__main__':
    # Add some default farms for testing
    farms_db.append({
        'id': 1,
        'name': 'North Field Farm',
        'location': 'Sector A1',
        'boundaries': {'min_x': -2, 'min_y': -2, 'max_x': 2, 'max_y': 2},
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
    })
    
    print("🚁 Farm Drone Inspection Server Starting...")
    print("📡 Server running on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)