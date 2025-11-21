# FILE: app/services/physics_service.py
import subprocess
import json
import os
import re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
SIM_SCRIPT_PATH = os.path.join(PROJECT_ROOT, "simulation", "calc_twr.py")

def infer_voltage_from_kv(kv):
    """Heuristic: Guess battery voltage based on Motor KV if missing."""
    if not kv or kv == 0: return 14.8 # Default to 4S
    if kv > 12000: return 3.7   # 1S (Tiny Whoop)
    if kv > 5000: return 7.4    # 2S-3S (Cinewhoop)
    if kv > 2200: return 14.8   # 4S (Freestyle)
    return 22.2                 # 6S (High Performance/Long Range)

def infer_prop_size_from_motor(motor_name):
    """Heuristic: Guess prop size from motor stator size."""
    name = motor_name.lower()
    if "0802" in name or "0702" in name: return 1.2 # 31mm
    if "110" in name or "120" in name: return 2.5
    if "1404" in name or "150" in name: return 3.5
    if "220" in name or "230" in name: return 5.0
    if "280" in name: return 7.0
    return 5.0 # Default to standard 5 inch

def run_physics_simulation(bom_data: list) -> dict:
    """
    Prepares BOM data for the simulation script.
    Includes robust fallback logic for missing specs.
    """
    total_weight = 0.0
    
    # Critical Flight Vars
    max_thrust_per_motor = 0.0
    motor_kv = 0
    battery_voltage = 0.0
    battery_capacity = 0
    prop_diam_inch = 0.0
    prop_pitch = 3.5 # Average pitch
    num_motors = 4

    if not bom_data:
        return {"error": "BOM is empty", "twr": 0}

    for item in bom_data:
        pt = str(item.get("part_type", "")).lower()
        name = str(item.get("product_name", "")).lower()
        specs = item.get("engineering_specs", {})
        
        # --- 1. WEIGHT AGGREGATION ---
        # Try to find weight in text, else use heuristic
        weight_match = re.search(r"(\d+\.?\d*)\s?g\b", name)
        weight = float(weight_match.group(1)) if weight_match else 0.0
        
        if weight == 0:
            # Fallback Weight Table
            if "motor" in pt: weight = 35.0 if "2" in name else 5.0
            elif "frame" in pt: weight = 120.0 if "5" in name else 30.0
            elif "fc" in pt or "stack" in pt: weight = 15.0
            elif "camera" in pt: weight = 8.0
            elif "battery" in pt: weight = 200.0 # Heavy fallback
            elif "prop" in pt: weight = 5.0
        
        # Multiplier for motors/props
        if "motor" in pt or "prop" in pt:
            total_weight += (weight * 4)
        else:
            total_weight += weight

        # --- 2. SPEC EXTRACTION ---
        
        # MOTORS
        if "motor" in pt:
            # Extract KV
            if not motor_kv:
                kv_match = re.search(r"(\d{3,5})\s?kv", name)
                if kv_match: motor_kv = int(kv_match.group(1))
            
            # Estimate Thrust (Gram) if not in specs
            # Simple linear regression approximation based on stator volume would be better,
            # but for now we step-function it.
            if max_thrust_per_motor == 0:
                if "28" in name: max_thrust_per_motor = 2000.0
                elif "2306" in name or "2207" in name: max_thrust_per_motor = 1300.0
                elif "1404" in name: max_thrust_per_motor = 400.0
                elif "0802" in name: max_thrust_per_motor = 40.0
                else: max_thrust_per_motor = 1000.0 # Generic 5" motor
        
        # BATTERY
        elif "battery" in pt:
            # Cells (S)
            if battery_voltage == 0:
                cell_match = re.search(r"(\d)s", name)
                if cell_match: 
                    battery_voltage = int(cell_match.group(1)) * 3.7
            
            # Capacity (mAh)
            if battery_capacity == 0:
                cap_match = re.search(r"(\d{3,5})\s?mah", name)
                if cap_match: battery_capacity = int(cap_match.group(1))

        # PROPS
        elif "prop" in pt:
            if prop_diam_inch == 0:
                if specs.get("diameter_mm"):
                    prop_diam_inch = specs.get("diameter_mm") / 25.4
                else:
                    # Try extract from name "5x4.3x3" or "5043"
                    dim_match = re.search(r"\b(\d)(\d)(\d{2})", name) # e.g. 5043
                    if dim_match:
                        prop_diam_inch = float(dim_match.group(1))
                    else:
                         # Try "5 inch"
                        inch_match = re.search(r"(\d\.?\d?)\s?inch", name)
                        if inch_match: prop_diam_inch = float(inch_match.group(1))

    # --- 3. FINAL SANITIZATION (The Crash Proofing) ---
    if total_weight < 50: total_weight = 400.0 # Assume standard 5" AUW if calculation failed
    if motor_kv == 0: motor_kv = 1800 # Default Freestyle KV
    if battery_voltage == 0: battery_voltage = infer_voltage_from_kv(motor_kv)
    if prop_diam_inch == 0: 
        # Find motor name to guess prop
        motor_name = next((item.get("product_name") for item in bom_data if "motor" in item.get("part_type", "").lower()), "")
        prop_diam_inch = infer_prop_size_from_motor(motor_name)

    # Recalculate thrust if we relied on generic defaults, scaling by voltage
    # (Thrust roughly proportional to Voltage^2 for same motor/prop)
    # Base Ref: 1800KV on 4S (16V) ~ 1200g thrust
    ref_voltage = 16.0
    thrust_scalar = (battery_voltage / ref_voltage)
    if max_thrust_per_motor == 1000.0: # If using default
        max_thrust_per_motor = max_thrust_per_motor * thrust_scalar

    sim_input = {
        "total_weight_g": int(total_weight),
        "max_thrust_g": int(max_thrust_per_motor),
        "num_motors": num_motors,
        "battery_capacity_mah": battery_capacity or 1300,
        "motor_kv": motor_kv,
        "voltage": battery_voltage,
        "prop_diameter_inch": prop_diam_inch,
        "prop_pitch_inch": prop_pitch
    }
    
    try:
        process = subprocess.Popen(
            ["python3", SIM_SCRIPT_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=json.dumps(sim_input))
        if stderr: 
            print(f"Physics STDERR: {stderr}")
            return {"error": "Simulation script error", "debug": stderr}
            
        return json.loads(stdout)
    except Exception as e:
        print(f"Physics Exception: {e}")
        return {"error": str(e)}