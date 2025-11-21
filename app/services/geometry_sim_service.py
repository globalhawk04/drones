# FILE: app/services/geometry_sim_service.py
import math

def run_geometric_simulation(specs, physical_constraints):
    """
    Phase 2 Simulation: Geometric Integrity.
    Performs spatial analysis to detect collisions and performance characteristics.
    
    Args:
        specs: Dict containing CAD parameters (wheelbase, prop_diameter, etc.)
        physical_constraints: Dict containing limits (optional)
        
    Returns:
        Dict with status (PASS/FAIL), errors, warnings, and calculated metrics.
    """
    
    # 1. Extract Geometry & Sanitize
    wheelbase = float(specs.get('wheelbase', 225)) # Diagonal distance in mm
    prop_diam_mm = float(specs.get('prop_diameter_mm', 127)) # Default 5 inch
    
    # If weight not provided, assume a standard freestyle AUW (All Up Weight)
    total_weight_g = float(specs.get('total_weight_g', 600))
    
    report = {
        "status": "PASS",
        "warnings": [],
        "errors": [],
        "metrics": {}
    }
    
    # --- CHECK 1: Propeller Collision (The "Prop Strike" Check) ---
    # In a True-X frame, the distance between adjacent motor shafts (side length)
    # is derived from the diagonal wheelbase.
    # Side Length = Wheelbase / sqrt(2)
    side_dist = wheelbase / 1.41421356
    
    # The Gap is Side Length minus Prop Diameter
    prop_gap = side_dist - prop_diam_mm
    
    if prop_gap < 1.0:
        report['errors'].append(f"CRITICAL: Propellers collide! Gap is {round(prop_gap, 2)}mm. (Wheelbase {wheelbase}mm vs Prop {prop_diam_mm}mm).")
        report['status'] = "FAIL"
    elif prop_gap < 5.0:
        report['warnings'].append(f"Prop gap is extremely tight ({round(prop_gap, 2)}mm). Turbulence and prop-wash likely.")
    elif prop_gap > 50.0:
         report['warnings'].append(f"Frame is oversized for these props (Gap: {round(prop_gap, 2)}mm). Consider larger props or smaller frame.")

    # --- CHECK 2: Camera Field of View Obstruction ---
    # Heuristic: Is the prop arc significantly forward of the main body?
    
    fc_mount_size = float(specs.get('fc_mounting_mm', 30.5))
    # Estimate main body chassis length based on stack size + room for camera/VTX
    body_length_est = fc_mount_size + 45.0 
    
    # Distance from center to front edge of chassis
    dist_center_to_front = body_length_est / 2
    
    # Motor forward position (X coordinate) relative to center
    motor_x = side_dist / 2
    
    # Does the prop tip cross the front plane of the camera?
    # Prop tip X = Motor X + Radius
    prop_tip_x = motor_x + (prop_diam_mm / 2)
    
    # If the motor shaft is nearly flush with the front of the body, 
    # the prop definitely spins in view.
    if motor_x > (dist_center_to_front - 10):
         report['warnings'].append("Propellers are positioned forward in the camera FOV (Props in View).")

    # --- CHECK 3: Disk Loading (Flight Feel) ---
    # Metric: Grams per square centimeter of prop area.
    # Area = 4 * (pi * r^2)
    
    radius_cm = (prop_diam_mm / 10.0) / 2.0
    area_one_prop_cm2 = math.pi * (radius_cm ** 2)
    total_disc_area_cm2 = area_one_prop_cm2 * 4.0
    
    if total_disc_area_cm2 > 0:
        disk_loading = total_weight_g / total_disc_area_cm2
    else:
        disk_loading = 0
        
    # Interpret Flight Characteristics
    load_feel = "Unknown"
    if disk_loading < 0.4: load_feel = "Glider / Ultralight (Floaty)"
    elif disk_loading < 0.7: load_feel = "Standard Freestyle (Balanced)"
    elif disk_loading < 1.0: load_feel = "Racing / Cinematic (Locked In)"
    else: load_feel = "Heavy Lift / Brick (Inefficient)"

    report['metrics'] = {
        "prop_gap_mm": round(prop_gap, 2),
        "disk_loading_g_cm2": round(disk_loading, 2),
        "flight_feel_prediction": load_feel,
        "geometric_efficiency": round(prop_gap / prop_diam_mm, 2)
    }
    
    return report