import pybullet as p
import pybullet_data
import time
import numpy as np
import math
import random
import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms, models
from ultralytics import YOLO
import os
import glob
import threading
import queue
import json

# Import Local Control Classes
try:
    from DSLPIDControl import DSLPIDControl
    from enums import DroneModel
except ImportError:
    print("⚠️ Control scripts missing. Ensure DSLPIDControl.py and enums.py are in the folder.")
    exit()

# ================= CONFIGURATION =================
TEXTURE_DIR = "test/images"   
YOLO_PATH = "best.pt"       
GNN_PATH = "gnn_deep_final.pth" 
DRONE_URDF = "cf2p.urdf"

SIM_HZ = 240.
CTRL_HZ = 48.
CTRL_TIMESTEP = 1.0 / CTRL_HZ
SIM_STEPS = int(SIM_HZ / CTRL_HZ)

IMG_WIDTH, IMG_HEIGHT = 640, 480
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

CLASS_NAMES = [
    "Early Blight", "Healthy", "Late Blight", "Leaf Miner", 
    "Leaf Mold", "Mosaic Virus", "Septoria", "Spider Mites", 
    "Yellow Leaf Curl", "Bacterial Spot"
]

# Color mapping for diseases
DISEASE_COLORS = {
    "HEALTHY": (0, 255, 0),
    "EARLY BLIGHT": (0, 165, 255),
    "LATE BLIGHT": (0, 0, 255),
    "LEAF MINER": (255, 0, 0),
    "LEAF MOLD": (255, 165, 0),
    "MOSAIC VIRUS": (128, 0, 128),
    "SEPTORIA": (255, 192, 203),
    "SPIDER MITES": (165, 42, 42),
    "YELLOW LEAF CURL": (0, 255, 255),
    "BACTERIAL SPOT": (139, 69, 19),
    "NO DETECTION": (128, 128, 128)
}

# ================= AI MODELS =================
class DeepLeafMPNN(nn.Module):
    def __init__(self, hidden_dim=128, num_classes=10):
        super().__init__()
        resnet = models.resnet18(weights=None) 
        self.cnn = nn.Sequential(*list(resnet.children())[:-1]) 
        self.cnn_fc = nn.Linear(512, hidden_dim)
        self.geom_enc = nn.Linear(6, hidden_dim)
        self.fusion = nn.Linear(hidden_dim * 2, hidden_dim)
        self.msg = nn.Linear(hidden_dim, hidden_dim)
        self.gru = nn.GRUCell(hidden_dim, hidden_dim)
        self.head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, num_classes))
    
    def forward(self, crops, geom, A, batch_idx):
        vis_feat = F.relu(self.cnn_fc(self.cnn(crops).squeeze()))
        if len(vis_feat.shape)==1: vis_feat=vis_feat.unsqueeze(0)
        geo_feat = F.relu(self.geom_enc(geom))
        h = F.relu(self.fusion(torch.cat([vis_feat, geo_feat], dim=1)))
        deg = A.sum(dim=1, keepdim=True).clamp(min=1.0); A_norm = A / deg
        for _ in range(2): h = self.gru(A_norm @ self.msg(h), h)
        hg = h.mean(dim=0, keepdim=True) 
        return self.head(hg)

# ================= ENVIRONMENT GENERATION =================
def create_complex_plant(pos, img_files=None):
    """Create a realistic plant with stem and leaves"""
    stem_vis = p.createVisualShape(
        p.GEOM_CYLINDER, 
        radius=0.015, 
        length=0.5, 
        rgbaColor=[0.2, 0.6, 0.2, 1]
    )
    stem_col = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.015, height=0.5)
    p.createMultiBody(
        baseVisualShapeIndex=stem_vis,
        baseCollisionShapeIndex=stem_col,
        basePosition=[pos[0], pos[1], 0.25]
    )

    num_leaves = 8
    height_step = 0.06 
    current_height = 0.1 
    
    for i in range(num_leaves):
        angle = i * 1.6
        dist_from_stem = 0.12 
        lx = pos[0] + math.cos(angle) * dist_from_stem
        ly = pos[1] + math.sin(angle) * dist_from_stem
        lz = current_height
        leaf_orn = p.getQuaternionFromEuler([0.3, 0, angle]) 
        
        if img_files and len(img_files) > 0:
            try:
                img_path = random.choice(img_files)
                tex_id = p.loadTexture(img_path)
                leaf_visual = p.createVisualShape(
                    p.GEOM_BOX, 
                    halfExtents=[0.1, 0.1, 0.001], 
                    rgbaColor=[1, 1, 1, 1]
                )
                leaf_id = p.createMultiBody(
                    baseVisualShapeIndex=leaf_visual, 
                    basePosition=[lx, ly, lz], 
                    baseOrientation=leaf_orn
                )
                p.changeVisualShape(leaf_id, -1, textureUniqueId=tex_id)
            except:
                leaf_visual = p.createVisualShape(
                    p.GEOM_BOX, 
                    halfExtents=[0.1, 0.1, 0.001], 
                    rgbaColor=[0.1, 0.8, 0.2, 1]
                )
                p.createMultiBody(
                    baseVisualShapeIndex=leaf_visual, 
                    basePosition=[lx, ly, lz], 
                    baseOrientation=leaf_orn
                )
        else:
            leaf_visual = p.createVisualShape(
                p.GEOM_BOX, 
                halfExtents=[0.1, 0.1, 0.001], 
                rgbaColor=[0.1, 0.8, 0.2, 1]
            )
            p.createMultiBody(
                baseVisualShapeIndex=leaf_visual, 
                basePosition=[lx, ly, lz], 
                baseOrientation=leaf_orn
            )
        
        current_height += height_step

def setup_pro_field(field_min, field_max):
    """Setup professional field with plants"""
    print("🌱 Planting field...")
    
    img_files = []
    if os.path.exists(TEXTURE_DIR):
        img_files = glob.glob(os.path.join(TEXTURE_DIR, "*.jpg")) + \
                   glob.glob(os.path.join(TEXTURE_DIR, "*.jpeg"))
    
    x_positions = np.arange(field_min[0], field_max[0], 1.2) 
    y_positions = np.arange(field_min[1], field_max[1], 1.2)
    
    count = 0
    for x in x_positions:
        for y in y_positions:
            nx = x + random.uniform(-0.15, 0.15)
            ny = y + random.uniform(-0.15, 0.15)
            create_complex_plant([nx, ny, 0], img_files if img_files else None)
            count += 1
    
    print(f"🌱 Planted {count} plants")
    return 0.8

def setup_simulation_gui(drone_urdf_path=DRONE_URDF):
    """Setup PyBullet simulation WITH GUI"""
    if p.isConnected():
        p.disconnect()
    
    p.connect(p.GUI)  # GUI MODE - visible window
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.81)
    p.setPhysicsEngineParameter(fixedTimeStep=1.0/240.0)
    
    plane_id = p.loadURDF("plane.urdf")
    
    start_pos = [0, 0, 0.1]
    start_orn = p.getQuaternionFromEuler([0, 0, 0])
    drone_id = p.loadURDF(drone_urdf_path, start_pos, start_orn)
    
    return drone_id, plane_id

def get_drone_view(drone_id):
    """Capture camera view from drone perspective"""
    pos, orn = p.getBasePositionAndOrientation(drone_id)
    rot_mat = np.array(p.getMatrixFromQuaternion(orn)).reshape(3, 3)
    cam_pos = pos + np.dot(rot_mat, [0, 0, -0.1])
    target = pos + np.dot(rot_mat, [0, 0, -1.0])
    up = np.dot(rot_mat, [1, 0, 0])
    
    view_mat = p.computeViewMatrix(cam_pos, target, up)
    proj_mat = p.computeProjectionMatrixFOV(60, IMG_WIDTH/IMG_HEIGHT, 0.1, 100)
    
    w, h, rgb, _, _ = p.getCameraImage(
        IMG_WIDTH, IMG_HEIGHT, 
        view_mat, proj_mat,
        renderer=p.ER_BULLET_HARDWARE_OPENGL
    )
    rgb = np.array(rgb, dtype=np.uint8).reshape((IMG_HEIGHT, IMG_WIDTH, 4))
    return cv2.cvtColor(rgb[:,:,:3], cv2.COLOR_RGB2BGR)

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

# ================= DISEASE DETECTION MAP =================

class DiseaseDetectionMap:
    def __init__(self, field_min, field_max, cell_size=0.5):
        self.field_min = field_min
        self.field_max = field_max
        self.cell_size = cell_size
        
        # Create grid
        self.width = int((field_max[0] - field_min[0]) / cell_size) + 1
        self.height = int((field_max[1] - field_min[1]) / cell_size) + 1
        
        # Store detections: (x, y, disease, confidence)
        self.detections = []
        self.grid = {}
        self.lock = threading.Lock()
    
    def add_detection(self, x, y, disease, confidence):
        """Add a disease detection at location"""
        with self.lock:
            self.detections.append({
                'x': x,
                'y': y,
                'disease': disease,
                'confidence': confidence,
                'timestamp': time.time()
            })
            
            # Also store in grid for heatmap
            grid_x = int((x - self.field_min[0]) / self.cell_size)
            grid_y = int((y - self.field_min[1]) / self.cell_size)
            
            key = (grid_x, grid_y)
            if key not in self.grid:
                self.grid[key] = []
            self.grid[key].append({
                'disease': disease,
                'confidence': confidence
            })
    
    def get_summary(self):
        """Get summary of all detections"""
        with self.lock:
            summary = {}
            for detection in self.detections:
                disease = detection['disease']
                if disease not in summary:
                    summary[disease] = {
                        'count': 0,
                        'avg_confidence': 0,
                        'locations': []
                    }
                summary[disease]['count'] += 1
                summary[disease]['avg_confidence'] += detection['confidence']
                summary[disease]['locations'].append({
                    'x': round(detection['x'], 2),
                    'y': round(detection['y'], 2)
                })
            
            # Calculate averages
            for disease in summary:
                if summary[disease]['count'] > 0:
                    summary[disease]['avg_confidence'] = round(
                        summary[disease]['avg_confidence'] / summary[disease]['count'], 2
                    )
            
            return summary
    
    def get_all_detections(self):
        """Get all detections as list"""
        with self.lock:
            return json.loads(json.dumps(self.detections, default=str))
    
    def create_heatmap_image(self, width=600, height=600):
        """Create heatmap visualization"""
        heatmap = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Draw background (field area)
        heatmap[:, :] = (240, 240, 240)
        
        # Draw grid
        cell_pixel_w = width / self.width
        cell_pixel_h = height / self.height
        
        for i in range(self.width + 1):
            x = int(i * cell_pixel_w)
            cv2.line(heatmap, (x, 0), (x, height), (200, 200, 200), 1)
        
        for i in range(self.height + 1):
            y = int(i * cell_pixel_h)
            cv2.line(heatmap, (0, y), (width, y), (200, 200, 200), 1)
        
        # Draw detections
        with self.lock:
            for detection in self.detections:
                # Convert world coordinates to pixel coordinates
                rel_x = (detection['x'] - self.field_min[0]) / (self.field_max[0] - self.field_min[0])
                rel_y = (detection['y'] - self.field_min[1]) / (self.field_max[1] - self.field_min[1])
                
                px = int(rel_x * width)
                py = int(rel_y * height)
                
                # Clamp to bounds
                px = max(0, min(width - 1, px))
                py = max(0, min(height - 1, py))
                
                disease = detection['disease']
                color = DISEASE_COLORS.get(disease, (128, 128, 128))
                
                # Draw circle with disease color
                cv2.circle(heatmap, (px, py), 8, color, -1)
                cv2.circle(heatmap, (px, py), 8, (0, 0, 0), 2)
        
        return heatmap

# ================= NAVIGATION =================
def get_sweep_waypoints(start_pos, field_min, field_max, z_hover, sweep_step):
    """Generate sweep waypoints for the field"""
    waypoints = []
    
    waypoints.append(np.array([start_pos[0], start_pos[1], z_hover]))
    waypoints.append(np.array([field_min[0], field_min[1], z_hover]))

    x_min, y_min = field_min
    x_max, y_max = field_max
    current_y = y_min
    going_right = True

    while current_y <= y_max:
        x_start = x_min if going_right else x_max
        x_end = x_max if going_right else x_min
        
        waypoints.append(np.array([x_start, current_y, z_hover]))
        waypoints.append(np.array([x_end, current_y, z_hover]))
        
        current_y += sweep_step
        
        if current_y <= y_max + sweep_step:
            waypoints.append(np.array([x_end, current_y, z_hover]))
        
        going_right = not going_right

    waypoints.append(np.array([start_pos[0], start_pos[1], z_hover]))
    waypoints.append(np.array([start_pos[0], start_pos[1], 0.05]))
    
    return waypoints

# ================= MAIN SIMULATION =================
def run_drone_simulation_flask(farm, sim_state):
    """Run drone simulation integrated with Flask server (WITH GUI)"""
    print(f"[SIMULATOR] Starting mission for {farm['name']}")
    
    sim_state.is_running = True
    sim_state.status = "flying"
    sim_state.current_waypoint = 0
    sim_state.ai_diagnosis = "INITIALIZING..."
    
    # Initialize disease detection map
    bounds = farm['boundaries']
    field_min = [bounds['min_x'], bounds['min_y']]
    field_max = [bounds['max_x'], bounds['max_y']]
    disease_map = DiseaseDetectionMap(field_min, field_max, cell_size=0.5)
    
    # Load AI models if available
    detector = None
    gnn = None
    transform = None
    ai_enabled = False
    
    try:
        if os.path.exists(YOLO_PATH):
            detector = YOLO(YOLO_PATH)
            print("✅ YOLO model loaded")
        
        if os.path.exists(GNN_PATH):
            gnn = DeepLeafMPNN(num_classes=10).to(DEVICE)
            gnn.load_state_dict(torch.load(GNN_PATH, map_location=DEVICE, weights_only=False))
            gnn.eval()
            print("✅ GNN model loaded")
            
            transform = transforms.Compose([
                transforms.ToPILImage(), 
                transforms.Resize((64, 64)),
                transforms.ToTensor(), 
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
            ])
            
            ai_enabled = detector is not None and gnn is not None
            print(f"✅ AI Detection: {'ENABLED' if ai_enabled else 'DISABLED'}")
    except Exception as e:
        print(f"⚠️ AI initialization failed: {e}")
        ai_enabled = False
    
    try:
        # Setup simulation WITH GUI
        drone_id, _ = setup_simulation_gui()
        sim_state.drone_id = drone_id
        draw_field_boundaries(field_min, field_max)
        
        # Setup field
        plant_height = setup_pro_field(field_min, field_max)
        
        # Flight parameters
        HOVER_ALTITUDE = plant_height + 0.6
        SWEEP_STEP = 0.8
        CRUISE_SPEED = 0.5
        WAIT_TIME_AT_CORNER = 1.0
        
        start_x = field_min[0] - 1.0
        start_y = field_min[1] - 1.0
        start_pos = [start_x, start_y, 0.2]
        
        waypoints = get_sweep_waypoints(start_pos, field_min, field_max, HOVER_ALTITUDE, SWEEP_STEP)
        sim_state.total_waypoints = len(waypoints)
        
        ctrl = DSLPIDControl(drone_model=DroneModel.CF2P)
        
        # Trajectory state
        current_wp_idx = 0
        virtual_pos = np.array(start_pos)
        target_vel = np.zeros(3)
        wait_timer = 0.0
        is_waiting = False
        camera_frame_counter = 0
        
        abort_initiated = False
        
        print(f"[SIMULATOR] Mission setup complete. Waypoints: {len(waypoints)}")
        
        while current_wp_idx < len(waypoints):
            # Check for abort command
            try:
                cmd = sim_state.command_queue.get_nowait()
                if cmd == 'abort' and not abort_initiated:
                    print("[SIMULATOR] Mission aborted by user")
                    sim_state.status = "returning_home"
                    abort_initiated = True
                    
                    cur_pos_abort, _ = p.getBasePositionAndOrientation(drone_id)
                    return_home_waypoints = [
                        np.array([cur_pos_abort[0], cur_pos_abort[1], HOVER_ALTITUDE]),
                        np.array([start_x, start_y, HOVER_ALTITUDE]),
                        np.array([start_x, start_y, 0.05])
                    ]
                    
                    waypoints = return_home_waypoints
                    current_wp_idx = 0
                    virtual_pos = np.array([cur_pos_abort[0], cur_pos_abort[1], cur_pos_abort[2]])
                    is_waiting = False
                    wait_timer = 0.0
            except queue.Empty:
                pass
            
            # Handle pause/stall
            while sim_state.is_paused:
                time.sleep(0.01)
            
            # Get drone state
            cur_pos, cur_quat = p.getBasePositionAndOrientation(drone_id)
            cur_vel, cur_ang_vel = p.getBaseVelocity(drone_id)
            
            # Update global state
            sim_state.current_position = list(cur_pos)
            sim_state.current_waypoint = current_wp_idx
            
            # Navigation logic
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
            
            # PID Control
            rpm, _, _ = ctrl.computeControl(
                control_timestep=CTRL_TIMESTEP,
                cur_pos=np.array(cur_pos),
                cur_quat=np.array(cur_quat),
                cur_vel=np.array(cur_vel),
                cur_ang_vel=np.array(cur_ang_vel),
                target_pos=virtual_pos,
                target_vel=target_vel
            )
            
            # Capture camera and run AI (throttled to ~10 FPS)
            camera_frame_counter += 1
            if camera_frame_counter % 5 == 0:
                try:
                    frame = get_drone_view(drone_id)
                    
                    # Run AI detection if enabled
                    if ai_enabled and not abort_initiated:
                        results = detector(frame, verbose=False, conf=0.15)[0]
                        boxes = results.boxes.xyxy.cpu().numpy()
                        
                        if len(boxes) > 0:
                            crops, geom = [], []
                            for box in boxes:
                                x1, y1, x2, y2 = map(int, box)
                                if x2 > x1 and y2 > y1:
                                    c = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
                                    crops.append(transform(c))
                                    geom.append([x1/640, y1/480, x2/640, y2/480, 1.0, 1.0])
                            
                            if len(crops) > 0:
                                batch_crops = torch.stack(crops).to(DEVICE)
                                batch_geom = torch.tensor(geom).float().to(DEVICE)
                                N = len(crops)
                                adj = torch.zeros(N, N).to(DEVICE)
                                batch_idx = torch.zeros(N, dtype=torch.long).to(DEVICE)
                                
                                with torch.no_grad():
                                    logits = gnn(batch_crops, batch_geom, adj, batch_idx)
                                    pred_idx = logits.argmax(dim=1).item()
                                    confidence = torch.softmax(logits, dim=1)[0, pred_idx].item()
                                    diagnosis_text = CLASS_NAMES[pred_idx].upper()
                                    
                                    sim_state.ai_diagnosis = diagnosis_text
                                    sim_state.ai_confidence = round(confidence * 100, 1)
                                    
                                    # Add to disease map with current drone position
                                    disease_map.add_detection(
                                        cur_pos[0], 
                                        cur_pos[1], 
                                        diagnosis_text, 
                                        confidence
                                    )
                        else:
                            sim_state.ai_diagnosis = "NO DETECTION"
                    
                    # Add status overlay
                    cv2.rectangle(frame, (0, 0), (640, 80), (0, 0, 0), -1)
                    status_text = f"Status: {sim_state.status.upper()} | WP: {current_wp_idx}/{len(waypoints)}"
                    cv2.putText(frame, status_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    
                    if ai_enabled and sim_state.ai_diagnosis != "SCANNING...":
                        ai_text = f"AI: {sim_state.ai_diagnosis}"
                        if sim_state.ai_confidence > 0:
                            ai_text += f" ({sim_state.ai_confidence}%)"
                        color = (0, 255, 0) if sim_state.ai_diagnosis == "HEALTHY" else (0, 0, 255)
                        cv2.putText(frame, ai_text, (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    
                    with sim_state.camera_lock:
                        sim_state.camera_frame = frame
                except Exception as e:
                    print(f"[SIMULATOR] Camera/AI error: {e}")
            
            # Physics stepping
            forces = ctrl.KF * (rpm ** 2)
            for _ in range(SIM_STEPS):
                p.applyExternalForce(drone_id, 0, [0, 0, forces[0]], [0, 0, 0], p.LINK_FRAME)
                p.applyExternalForce(drone_id, 1, [0, 0, forces[1]], [0, 0, 0], p.LINK_FRAME)
                p.applyExternalForce(drone_id, 2, [0, 0, forces[2]], [0, 0, 0], p.LINK_FRAME)
                p.applyExternalForce(drone_id, 3, [0, 0, forces[3]], [0, 0, 0], p.LINK_FRAME)
                p.stepSimulation()
                time.sleep(1.0 / SIM_HZ)
        
        if abort_initiated:
            sim_state.status = "aborted"
            print(f"[SIMULATOR] Mission aborted")
        else:
            sim_state.status = "completed"
            print(f"[SIMULATOR] Mission completed for {farm['name']}")
        
        # Store disease map results in sim_state
        sim_state.disease_map = disease_map
        
        # Let physics settle
        for _ in range(100):
            p.stepSimulation()
            time.sleep(1.0 / SIM_HZ)
    
    except Exception as e:
        print(f"[SIMULATOR] Error: {e}")
        import traceback
        traceback.print_exc()
        sim_state.status = "error"
    
    finally:
        sim_state.is_running = False
        sim_state.is_paused = False
        sim_state.ai_diagnosis = "IDLE"
        sim_state.ai_confidence = 0.0
        with sim_state.camera_lock:
            sim_state.camera_frame = None
        if p.isConnected():
            p.disconnect()
        print("[SIMULATOR] Simulation ended")


if __name__ == "__main__":
    print("⚠️ This module is meant to be used with Flask server (app.py)")
    print("Run 'python app.py' instead")