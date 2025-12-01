# FILE: app/services/physics_service.py
import re
import math

# --- CONFIGURATION ---
GRAVITY = 9.81

# Fallback weights (in grams) for Robot Dog parts
FALLBACK_WEIGHTS = {
    "actuators": 60.0,         # Standard size servo (e.g. MG996R)
    "chassis_kit": 450.0,      # Carbon/Aluminum frame
    "servo_controller": 30.0,  # Driver board
    "single_board_computer": 80.0, # RPi + Heatsink
    "battery": 250.0,          # 3S LiPo
    "lidar_module": 170.0,
    "depth_camera": 100.0
}

# Default Geometry if CAD is missing (mm)
DEFAULT_FEMUR_LENGTH_MM = 100.0 

def _extract_number(text, default=0.0):
    """Robust extraction of numbers from dirty strings."""
    if isinstance(text, (int, float)): return float(text)
    if not text: return default
    try:
        match = re.search(r"(\d+(\.\d+)?)", str(text))
        return float(match.group(1)) if match else default
    except:
        return default

def _calculate_auw(bom):
    """Calculates All-Up-Weight in Grams."""
    total_g = 0.0
    
    for item in bom:
        cat = item.get('part_type', '').lower()
        qty = item.get('quantity', 1)
        
        # Heuristic: If quantity is 1 but it's "Actuators", assumes pack of 12? 
        # Usually the Sourcing agent will list quantity=12, but let's be safe.
        # Actually, let's rely on the BOM quantity provided by the agent.
        
        # Try finding weight in specs first
        weight = _extract_number(item.get('engineering_specs', {}).get('weight_g'))
        
        # Fallback to defaults
        if weight == 0:
            for k, v in FALLBACK_WEIGHTS.items():
                if k in cat:
                    weight = v
                    break
        
        total_g += (weight * qty)
        
    # Add 15% overhead for wiring, bolts, screws, feet
    return total_g * 1.15

def _calculate_torque_requirements(total_mass_kg, femur_length_mm):
    """
    Calculates the minimum torque required to stand/trot.
    
    Physics Logic:
    - Worst case static load is 2 legs supporting the body (Trot gait phase).
    - Torque = Force * Distance.
    - Force per leg = (Mass * Gravity) / 2.
    - Distance = Horizontal projection of the Femur (Upper Leg).
      Assuming a crouching stance (worst leverage), we use full femur length.
    """
    force_newtons = (total_mass_kg * GRAVITY) / 2.0
    lever_arm_cm = femur_length_mm / 10.0
    
    # Torque in kg.cm = (Force in kg) * (Distance in cm)
    # Force in Kg = Mass_kg / 2
    required_torque_kgcm = (total_mass_kg / 2.0) * lever_arm_cm
    
    return required_torque_kgcm

def generate_physics_config(bom):
    """
    Generates the Physics Profile for the Quadruped.
    Validates if the selected servos can actually lift the robot.
    """
    print("--> ⚙️  Physics Service: Calculating Torque & Statics...")
    
    # 1. Identify Critical Parts
    actuators = next((i for i in bom if 'actuator' in i.get('part_type', '').lower()), None)
    chassis = next((i for i in bom if 'chassis' in i.get('part_type', '').lower()), None)
    battery = next((i for i in bom if 'battery' in i.get('part_type', '').lower()), None)

    # 2. Calculate Mass
    mass_g = _calculate_auw(bom)
    mass_kg = mass_g / 1000.0
    
    # 3. Determine Geometry (Femur Length)
    # Ideally comes from Chassis specs or CAD, otherwise default
    femur_mm = DEFAULT_FEMUR_LENGTH_MM
    if chassis:
        # Sometimes chassis listings mention "Leg Length"
        specs = chassis.get('engineering_specs', {})
        if specs.get('femur_length_mm'):
            femur_mm = float(specs['femur_length_mm'])
    
    # 4. Calculate Torque Physics
    req_torque = _calculate_torque_requirements(mass_kg, femur_mm)
    
    # 5. Get Available Torque
    avail_torque = 0.0
    if actuators:
        specs = actuators.get('engineering_specs', {})
        avail_torque = _extract_number(specs.get('est_torque_kgcm') or specs.get('torque') or specs.get('stall_torque'))
    
    # 6. Safety Factor Analysis
    # Dynamic Safety Factor: We want at least 2.0x overhead for jumping/running.
    safety_margin = avail_torque / req_torque if req_torque > 0 else 0
    is_viable = safety_margin >= 1.5 # 1.5 is absolute minimum, 2.0+ preferred
    
    # 7. Payload Estimation
    # How much EXTRA weight can we add before hitting the 1.5 safety limit?
    # (Available / 1.5) = Max_Torque_Allowed
    # Max_Torque -> Max_Mass
    max_supported_torque = avail_torque / 1.5
    max_supported_mass = (max_supported_torque / (femur_mm / 10.0)) * 2.0
    est_payload_kg = max(0, max_supported_mass - mass_kg)

    config = {
        "mass_kg": round(mass_kg, 3),
        "geometry": {
            "femur_length_mm": femur_mm,
            "tibia_length_mm": femur_mm * 1.1 # Tibia usually slightly longer
        },
        "torque_physics": {
            "required_kgcm": round(req_torque, 2),
            "available_kgcm": round(avail_torque, 2),
            "safety_margin": round(safety_margin, 2),
            "est_payload_capacity_kg": round(est_payload_kg, 2)
        },
        "viability": {
            "is_mechanically_sound": is_viable,
            "failure_mode": None if is_viable else "Insufficient Torque"
        },
        "meta": {
            "est_runtime_min": _calculate_runtime(battery, mass_kg)
        }
    }
    
    print(f"   📊 Physics Ready: Mass={mass_kg}kg, Payload={est_payload_kg}kg, Margin={safety_margin:.1f}x")
    return config

def _calculate_runtime(battery_item, total_mass_kg):
    """
    Estimates runtime based on servo load.
    Walking robots consume power non-linearly (holding torque draws current).
    """
    if not battery_item: return 0
    
    mah = _extract_number(battery_item.get('engineering_specs', {}).get('capacity_mah'), 2200)
    
    # Heuristic: A robot dog draws approx 3 Amps per kg of weight during active walking.
    # This is a rough rule of thumb for hobby servos.
    avg_amp_draw = total_mass_kg * 3.0 
    if avg_amp_draw <= 0: return 0
    
    hours = (mah / 1000.0) / avg_amp_draw
    return round(hours * 60, 1)