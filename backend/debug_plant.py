import pybullet as p
import pybullet_data
import time
import os

def debug_plant():
    # 1. Setup
    p.connect(p.GUI)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
    p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 0) # No shadows
    
    # 2. Files
    obj_file = "tomato-plant.obj"
    texture_file = "tomato_diffuse.png"
    
    # 3. Check Files
    if not os.path.exists(obj_file):
        print(f"CRITICAL ERROR: {obj_file} not found!")
        return
    if not os.path.exists(texture_file):
        print(f"CRITICAL ERROR: {texture_file} not found!")
        return

    # 4. Load Plane
    p.loadURDF("plane.urdf")
    
    # 5. Load Texture
    tex_id = p.loadTexture(texture_file)
    print(f"Texture Loaded. ID: {tex_id}")

    # 6. Create Plant Visual
    print("Loading Mesh...")
    vis_id = p.createVisualShape(p.GEOM_MESH, fileName=obj_file, meshScale=[0.01, 0.01, 0.01])
    col_id = p.createCollisionShape(p.GEOM_MESH, fileName=obj_file, meshScale=[0.01, 0.01, 0.01])
    
    body_id = p.createMultiBody(baseMass=0, baseVisualShapeIndex=vis_id, baseCollisionShapeIndex=col_id, basePosition=[0,0,0])
    
    # --- TEST 1: PURE RED ---
    print("Test 1: Turning Plant RED (Checking mesh validity)...")
    p.changeVisualShape(body_id, -1, rgbaColor=[1, 0, 0, 1])
    p.addUserDebugText("TEST 1: RED", [0, 0, 1], [1, 0, 0], textSize=2)
    time.sleep(3)
    
    # --- TEST 2: TEXTURE ---
    print("Test 2: Applying Texture (Checking UV mapping)...")
    # Reset color to White so texture shows through
    p.changeVisualShape(body_id, -1, rgbaColor=[1, 1, 1, 1], textureUniqueId=tex_id)
    p.addUserDebugText("TEST 2: TEXTURE", [0, 0, 1.2], [0, 1, 0], textSize=2)
    time.sleep(10)

if __name__ == "__main__":
    debug_plant()