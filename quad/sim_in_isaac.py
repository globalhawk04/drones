# FILE: sim_in_isaac.py

from omni.isaac.kit import SimulationApp

# 1. Start App (Must happen before imports)
simulation_app = SimulationApp({"headless": False})

import omni
from omni.isaac.core import World
from omni.isaac.core.articulations import ArticulationView
from omni.isaac.core.utils.stage import add_reference_to_stage
import numpy as np
import os
import math

# Services
from app.services.ik_service import InverseKinematicsService

# --- CONFIGURATION ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
USD_EXPORT_DIR = os.path.join(CURRENT_DIR, "usd_export")

def main():
    world = World()
    world.scene.add_default_ground_plane()
    
    # Load the specific robot (hardcoded SKU for test, or dynamic)
    # In a real app, we'd iterate over fleet_data like the drone script
    sku = "robot_dog" 
    usd_path = os.path.join(USD_EXPORT_DIR, f"{sku}.usda")
    
    if not os.path.exists(usd_path):
        print(f"❌ Error: USD not found at {usd_path}. Run make_fleet.py first.")
        simulation_app.close()
        return

    # Add Reference to Stage
    prim_path = "/World/RanchDog_0"
    add_reference_to_stage(usd_path=usd_path, prim_path=prim_path)

    # --- ARTICULATION VIEW ---
    # This view allows us to control joints efficiently
    robot_view = ArticulationView(
        prim_paths_expr="/World/RanchDog_*", 
        name="ranch_dog_view"
    )
    world.scene.add(robot_view)
    
    world.reset()

    # --- CONTROLLER SETUP ---
    # Dimensions match CAD service defaults
    ik_solver = InverseKinematicsService(femur_len=0.1, tibia_len=0.1)
    
    # Neutral Stance (Standing height)
    stand_height = -0.18 # meters (below hip)
    
    print("--> 🐕 Simulation Started. Trot Gait Active.")

    while simulation_app.is_running():
        # Physics Step
        world.step(render=True)
        if not world.is_playing(): continue
        
        t = world.current_time
        
        # 1. Calculate Gait Phase
        # Diagonal pairs move together for Trot
        # Pair A: FR, RL
        # Pair B: FL, RR
        
        # Generate trajectories
        x_a, z_offset_a = ik_solver.generate_trot_path(t, stride_length=0.08, step_height=0.04)
        x_b, z_offset_b = ik_solver.generate_trot_path(t + 0.25, stride_length=0.08, step_height=0.04) # Phase shifted
        
        # 2. Solve IK for all 4 legs
        # Order in USD: usually alphabetical or defined by creation order. 
        # We need to map joint indices. For V1, we assume a fixed order:
        # [FR_Hip, FR_Knee, FL_Hip, FL_Knee, RR_Hip, RR_Knee, RL_Hip, RL_Knee]
        # NOTE: In ArticulationView, get_joint_names() helps debug order.
        
        # Target Positions (Relative to Hip)
        targets = [
            (x_a, stand_height + z_offset_a), # FR
            (x_b, stand_height + z_offset_b), # FL
            (x_b, stand_height + z_offset_b), # RR (Matches FL in Trot?) No, Trot is diagonal.
                                              # Trot: FR+RL sync, FL+RR sync.
            (x_a, stand_height + z_offset_a), # RL
        ]
        
        # Correct Trot Pairing:
        # FR (0) & RL (3) match
        # FL (1) & RR (2) match
        
        targets = [
            (x_a, stand_height + z_offset_a), # FR
            (x_b, stand_height + z_offset_b), # FL
            (x_b, stand_height + z_offset_b), # RR
            (x_a, stand_height + z_offset_a), # RL
        ]

        joint_commands = []
        
        for tx, tz in targets:
            hip_deg, knee_deg = ik_solver.solve_2dof(tx, abs(tz)) # tz is negative world, positive distance
            
            if hip_deg is not None:
                joint_commands.append(math.degrees(hip_deg))
                joint_commands.append(math.degrees(knee_deg))
            else:
                # Fallback if unreachable
                joint_commands.append(0)
                joint_commands.append(0)
                
        # 3. Apply to Sim
        # Convert to numpy array
        # Note: set_joint_position_targets expects Radian or Degree depending on USD metadata.
        # Usually Isaac API uses Radians/Meters unless specified. Let's try degrees first based on common servo logic,
        # but Isaac standard is Rads. Let's convert back to Rads for safety.
        
        cmds_rad = np.radians(np.array(joint_commands))
        
        # Broadcast to all robots in view
        # Shape: (num_robots, num_joints)
        num_robots = robot_view.count
        batch_cmds = np.tile(cmds_rad, (num_robots, 1))
        
        robot_view.set_joint_position_targets(batch_cmds)

    simulation_app.close()

if __name__ == "__main__":
    main()