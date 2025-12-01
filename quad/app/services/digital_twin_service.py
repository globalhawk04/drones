# FILE: app/services/digital_twin_service.py
import math
import re

def _extract_float(value, default=0.0):
    """Robust number extraction."""
    if value is None: return default
    if isinstance(value, (int, float)): return float(value)
    match = re.search(r"(\d+(\.\d+)?)", str(value))
    return float(match.group(1)) if match else default

def generate_environment_config(mission_profile):
    """
    Decides the Simulation Environment based on the Mission.
    Pivoted from City/Lab to Ranch/Mud scenarios.
    """
    mission_name = str(mission_profile.get("mission_name", "")).lower()
    requirements = str(mission_profile.get("key_requirements", [])).lower()
    
    # Default Lab
    env = {
        "type": "LAB_CLEAN",
        "sky_color": "#1a1a1a", 
        "ground_color": "#222222", 
        "physics_material": {"friction": 0.8, "restitution": 0.5}, # Standard concrete
        "obstacles": []
    }

    # Scenario 1: The Feed Mule (Mud & Heavy Loads)
    if "feed" in mission_name or "mule" in mission_name or "mud" in requirements:
        env["type"] = "RANCH_MUD_PEN"
        env["sky_color"] = "#87CEEB"
        env["ground_color"] = "#3e2723" # Muddy Brown
        env["physics_material"] = {"friction": 0.9, "restitution": 0.1} # Sticky, non-bouncy
        env["obstacles"] = [
            {"type": "FENCE_POST", "count": 10, "spacing": 2.0},
            {"type": "FEED_CUBE", "count": 1, "mass_kg": 10.0, "dims": [0.3, 0.3, 0.3]}, # The Target Payload
            {"type": "TROUGH", "pos": [5, 0, 0]}
        ]

    # Scenario 2: Fence Patrol (Distance & Vegetation)
    elif "fence" in mission_name or "patrol" in mission_name:
        env["type"] = "RANCH_GRASSLAND"
        env["sky_color"] = "#87CEEB"
        env["ground_color"] = "#33691e" # Grass Green
        env["physics_material"] = {"friction": 0.6, "restitution": 0.3} # Grass
        env["obstacles"] = [
            {"type": "FENCE_LINE", "length_m": 50},
            {"type": "ROCK", "count": 15, "scale_range": [0.1, 0.4]} # Trip hazards
        ]

    return env

def generate_scene_graph(mission_profile, bom):
    """
    Calculates the 3D Assembly Graph for a Quadruped.
    Used for Frontend Visualization (Three.js) and initial Sim Setup.
    """
    # 1. Identify Key Components
    parts = {p.get('part_type'): p for p in bom}
    chassis = parts.get('Chassis_Kit') or parts.get('Chassis')
    actuators = parts.get('Actuators')
    
    # 2. Extract Dimensions (Critical for IK Visualization)
    # Default to "Spot Micro" size
    body_l = 240.0
    body_w = 120.0
    femur_len = 100.0
    tibia_len = 110.0
    
    if chassis:
        specs = chassis.get('engineering_specs', {})
        body_l = _extract_float(specs.get('length_mm'), body_l)
        body_w = _extract_float(specs.get('width_mm'), body_w)
        femur_len = _extract_float(specs.get('femur_length_mm'), femur_len)
        tibia_len = _extract_float(specs.get('tibia_length_mm'), tibia_len)

    # 3. Construct Components List
    components = []
    
    # --- ROOT: CHASSIS ---
    # Placed at standing height (approx length of legs)
    stand_height = femur_len + tibia_len - 30 # Slightly bent knees
    
    components.append({
        "id": "chassis",
        "type": "CHASSIS",
        "visuals": chassis.get("visuals", {"primary_color_hex": "#333333"}),
        "dims": {"length": body_l, "width": body_w, "height": 60},
        "pos": [0, stand_height, 0],
        "rot": [0, 0, 0]
    })

    # --- LEGS (x4) ---
    # FL (1,1), FR (1,-1), RL (-1,1), RR (-1,-1)
    legs = [
        {"id": "FL", "x": 1, "z": 1},
        {"id": "FR", "x": 1, "z": -1},
        {"id": "RL", "x": -1, "z": 1},
        {"id": "RR", "x": -1, "z": -1},
    ]

    for leg in legs:
        # Hip Offset from Chassis Center
        hip_x = (body_l / 2.0) * leg['x']
        hip_z = (body_w / 2.0) * leg['z']
        
        # A. FEMUR (Upper Leg)
        # Connected to chassis at hip point
        # Visual rotation: pointing DOWN
        components.append({
            "id": f"femur_{leg['id']}",
            "type": "FEMUR",
            "parent_id": "chassis",
            "visuals": actuators.get("visuals", {"primary_color_hex": "#111111"}),
            "dims": {"length": femur_len, "width": 20},
            # Position relative to Chassis Center
            "pos": [hip_x, 0, hip_z], 
            "rot": [0, 0, 0] # Neutral pose
        })

        # B. TIBIA (Lower Leg)
        # Connected to Femur
        components.append({
            "id": f"tibia_{leg['id']}",
            "type": "TIBIA",
            "parent_id": f"femur_{leg['id']}",
            "visuals": {"primary_color_hex": "#555555"}, # Usually aluminum or carbon rod
            "dims": {"length": tibia_len, "width": 15},
            # Position relative to Femur End (Local space)
            # In a simplified graph, we might define absolute positions, 
            # but for a graph, parent-relative is better.
            "relative_pos": [0, -femur_len, 0], 
            "rot": [20, 0, 0] # Slight knee bend for style
        })

    # --- SENSORS & PAYLOAD ---
    # Add Lidar on top if present
    if parts.get('Lidar_Module'):
        components.append({
            "id": "lidar",
            "type": "SENSOR_LIDAR",
            "parent_id": "chassis",
            "visuals": {"primary_color_hex": "#000000"},
            "dims": {"radius": 35, "height": 20},
            "relative_pos": [body_l/3, 35, 0], # Front-top of chassis
            "rot": [0, 0, 0]
        })

    # --- GENERATE ENVIRONMENT ---
    env = generate_environment_config(mission_profile)

    return {
        "environment": env,
        "components": components,
        "kinematics_meta": {
            "total_mass_est_kg": 2.5, # Placeholder, would come from physics service
            "standing_height_mm": stand_height,
            "footprint_dims": [body_l + 100, body_w + 50]
        }
    }