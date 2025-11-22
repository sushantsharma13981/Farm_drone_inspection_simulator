import pybullet as p
import pybullet_data
import time
import numpy as np
import math
import random
from threading import Event

# Import local classes
from DSLPIDControl import DSLPIDControl
from BaseControl import DroneModel

# --- Mission Control Flags (Global Control) ---
mission_abort_flag = Event()
mission_pause_flag = Event()

# --- Simulation Constants ---
SIM_HZ = 240.
CTRL_HZ = 48.
CTRL_TIMESTEP = 1.0 / CTRL_HZ
SIM_STEPS = int(SIM_HZ / CTRL_HZ)


# --- Simulation Setup ---
def setup_simulation(drone_urdf_path):
    print("🔄 Connecting to PyBullet...")
    if p.isConnected():
        p.disconnect()
    p.connect(p.GUI)

    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.81)
    p.setPhysicsEngineParameter(fixedTimeStep=1.0 / SIM_HZ)

    planeId = p.loadURDF("plane.urdf")

    print(f"🚁 Loading drone: {drone_urdf_path}")
    droneId = p.loadURDF(drone_urdf_path, [0, 0, 0.1], p.getQuaternionFromEuler([0, 0, 0]))

    return droneId, planeId


def draw_field_boundaries(min_corner, max_corner, z=0.01):
    x_min, y_min = min_corner
    x_max, y_max = max_corner
    corners = [
        [x_min, y_min, z], [x_max, y_min, z],
        [x_max, y_max, z], [x_min, y_max, z]
    ]
    for i in range(4):
        p.addUserDebugLine(corners[i], corners[(i+1) % 4], [0, 1, 0], 3)


def draw_path(waypoints):
    for i in range(len(waypoints)-1):
        p.addUserDebugLine(waypoints[i], waypoints[i+1], [1, 0, 0], 2)


# --- Sweeping Path Planner ---
def get_sweep_waypoints(field_min, field_max, z_hover, sweep_step=0.75):
    waypoints = []
    waypoints.append(np.array([0, 0, z_hover]))  # takeoff
    waypoints.append(np.array([field_min[0], field_min[1], z_hover]))

    x_min, y_min = field_min
    x_max, y_max = field_max
    current_y = y_min
    direction = True

    while current_y <= y_max:
        xs = x_min if direction else x_max
        xe = x_max if direction else x_min
        waypoints += [
            np.array([xs, current_y, z_hover]),
            np.array([xe, current_y, z_hover])
        ]
        direction = not direction
        current_y += sweep_step

    waypoints.append(np.array([0, 0, z_hover]))  # return
    waypoints.append(np.array([0, 0, 0.05]))     # land
    return waypoints


# --- Mission Execution ---
def run_simulation(droneId, field_min, field_max):
    print("🚁 Mission Started → Sweep Mode ACTIVE")

    waypoints = get_sweep_waypoints(field_min, field_max, z_hover=1.0)
    draw_path(waypoints)
    ctrl = DSLPIDControl(drone_model=DroneModel.CF2P)

    idx = 0
    virtual_pos = np.array([0, 0, 0.1])
    vel_cmd = np.zeros(3)
    wait_timer = 0.0
    waiting = False

    while True:
        # ABORT request
        if mission_abort_flag.is_set():
            print("⚠️ ABORT received → landing...")
            target_ground = np.array([0, 0, 0.05])

            while True:
                cur_pos, cur_quat = p.getBasePositionAndOrientation(droneId)
                cur_vel, cur_ang_vel = p.getBaseVelocity(droneId)
                diff = target_ground - np.array(cur_pos)

                if np.linalg.norm(diff) < 0.05:
                    print("⛔ Aborted. Drone landed successfully.")
                    return

                vel_cmd = diff * 0.8
                rpm, _, _ = ctrl.computeControl(CTRL_TIMESTEP,
                                                np.array(cur_pos), np.array(cur_quat),
                                                np.array(cur_vel), np.array(cur_ang_vel),
                                                target_ground, vel_cmd)

                forces = ctrl.KF * (rpm**2)
                for i in range(4):
                    p.applyExternalForce(droneId, i, [0,0,forces[i]], [0,0,0], p.LINK_FRAME)

                p.stepSimulation()
                time.sleep(1./SIM_HZ)

        # PAUSE request
        if mission_pause_flag.is_set():
            # Freeze motion but keep gravity simulation
            p.stepSimulation()
            time.sleep(1.0 / SIM_HZ)
            continue

        # --- Path Logic ---
        if idx >= len(waypoints):
            print("🏁 Sweep Done → Landing!")
            time.sleep(1)
            return

        target = waypoints[idx]
        cur_pos, cur_quat = p.getBasePositionAndOrientation(droneId)
        cur_vel, cur_ang_vel = p.getBaseVelocity(droneId)

        dist = np.linalg.norm(target - virtual_pos)

        if waiting:
            wait_timer += CTRL_TIMESTEP
            if wait_timer > 1.5:
                waiting = False
                idx += 1
                wait_timer = 0.0
        elif dist < 0.05:
            waiting = True
            virtual_pos = target
            vel_cmd = np.zeros(3)
        else:
            direction = (target - virtual_pos) / dist
            vel_cmd = direction * 0.5
            virtual_pos += vel_cmd * CTRL_TIMESTEP

        # Controller + Physics
        rpm, _, _ = ctrl.computeControl(CTRL_TIMESTEP,
                                        np.array(cur_pos), np.array(cur_quat),
                                        np.array(cur_vel), np.array(cur_ang_vel),
                                        virtual_pos, vel_cmd)

        forces = ctrl.KF * (rpm**2)
        for _ in range(SIM_STEPS):
            for i in range(4):
                p.applyExternalForce(droneId, i, [0,0,forces[i]], [0,0,0], p.LINK_FRAME)
            p.stepSimulation()
            time.sleep(1.0 / SIM_HZ)
