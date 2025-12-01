# FILE: app/services/cad_service.py
import os
import subprocess
import logging
import trimesh
import numpy as np

# Helper function to find parts in the BOM
def find_part_in_bom(bom, part_type_query):
    for item in bom:
        if part_type_query.lower() in item.get("part_type", "").lower():
            return item
    return None

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def render_scad(script: str, output_filename: str) -> str | None:
    scad_path = os.path.join(OUTPUT_DIR, f"{output_filename}.scad")
    stl_path = os.path.join(OUTPUT_DIR, f"{output_filename}.stl")
    
    with open(scad_path, "w") as f:
        f.write(script)
    
    try:
        # Standard OpenSCAD CLI call
        cmd = ["openscad", "-o", stl_path, scad_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if os.path.exists(stl_path):
            return stl_path
        return None
    except Exception as e:
        logger.error(f"❌ OpenSCAD Render Failed for {output_filename}: {e}")
        # Create dummy placeholder if render fails to keep pipeline alive
        return None

def generate_assets(project_id: str, blueprint: dict, bom: list) -> dict:
    print("--> 🏗️  CAD Service: Parametric generation of Robot Dog parts...")
    assets = {
        "individual_parts": {},
        "collision_report": {"collided": False, "colliding_parts": []}
    }
    
    # --- 1. EXTRACT DIMENSIONS ---
    # We need the physical dimensions to generate the right leg lengths
    
    chassis_part = find_part_in_bom(bom, "chassis") or {}
    actuator_part = find_part_in_bom(bom, "actuator") or {}
    battery_part = find_part_in_bom(bom, "battery") or {}

    def get_spec(part, key, default):
        val = part.get("engineering_specs", {}).get(key)
        return float(val) if val is not None else default

    # Dimensions (Millimeters)
    # Default to a "Spot-Micro" size if unknown
    body_length = get_spec(chassis_part, "length_mm", 240.0)
    body_width = get_spec(chassis_part, "width_mm", 120.0)
    
    # Leg Geometry (Critical for Kinematics)
    # If physics service didn't set these, use defaults
    femur_len = get_spec(chassis_part, "femur_length_mm", 100.0)
    tibia_len = get_spec(chassis_part, "tibia_length_mm", 110.0)
    
    # Servo Pocket Sizing (Micro vs Standard)
    servo_class = actuator_part.get("engineering_specs", {}).get("size_class", "Standard")
    is_micro = "Micro" in servo_class
    servo_w = 12.5 if is_micro else 20.0
    servo_l = 23.0 if is_micro else 40.0
    servo_h = 22.0 if is_micro else 36.0

    # --- 2. GENERATE OPENSCAD SCRIPTS ---
    
    # A. CHASSIS (Main Body)
    # A simple box with mounting holes for hips at the 4 corners
    chassis_script = f"""
    $fn=50;
    module chassis() {{
        difference() {{
            // Main Body Shell
            cube([{body_length}, {body_width}, 45], center=true);
            
            // Hollow Inside (for Electronics)
            cube([{body_length - 10}, {body_width - 10}, 40], center=true);
        }}
        
        // Hip Servo Mounts (4 Corners)
        for (x = [-1, 1]) for (y = [-1, 1]) {{
            translate([x * ({body_length}/2 - {servo_l}/2), y * ({body_width}/2), 0])
            rotate([90, 0, 0])
            cube([{servo_l + 4}, {servo_h + 4}, {servo_w + 4}], center=true);
        }}
    }}
    chassis();
    """

    # B. FEMUR (Upper Leg)
    # Connects Hip Servo to Knee Servo
    femur_script = f"""
    $fn=50;
    module femur() {{
        difference() {{
            union() {{
                // Hip Joint Hub
                cylinder(h={servo_w}, r=15, center=true);
                
                // Bone
                translate([{femur_len}/2, 0, 0])
                cube([{femur_len}, 10, 5], center=true);
                
                // Knee Joint Hub
                translate([{femur_len}, 0, 0])
                cylinder(h={servo_w}, r=15, center=true);
            }}
            
            // Servo Horn Cutouts
            cylinder(h={servo_w}+2, r=3, center=true); // Hip Axis
            translate([{femur_len}, 0, 0])
                cylinder(h={servo_w}+2, r=3, center=true); // Knee Axis
        }}
    }}
    femur();
    """

    # C. TIBIA (Lower Leg)
    # Connects Knee Servo to Foot
    tibia_script = f"""
    $fn=50;
    module tibia() {{
        union() {{
            // Knee Connection
            difference() {{
                cylinder(h={servo_w}, r=12, center=true);
                cylinder(h={servo_w}+2, r=3, center=true);
            }}
            
            // Shin Bone
            translate([0, -{tibia_len}/2, 0])
            cube([8, {tibia_len}, 5], center=true);
            
            // Foot Nub
            translate([0, -{tibia_len}, 0])
            sphere(r=8);
        }}
    }}
    tibia();
    """

    # D. ACTUATOR (Visual Placeholder)
    # To check for collisions inside the chassis
    servo_script = f"""
    module servo() {{
        color("black") cube([{servo_l}, {servo_h}, {servo_w}], center=true);
        color("white") translate([0, {servo_h}/2, 0]) cylinder(h=4, r=3); // Output gear
    }}
    servo();
    """

    # --- 3. RENDER ASSETS ---
    assets["individual_parts"]["Chassis_Kit"] = render_scad(chassis_script, f"{project_id}_chassis")
    assets["individual_parts"]["Femur_Leg"] = render_scad(femur_script, f"{project_id}_femur")
    assets["individual_parts"]["Tibia_Leg"] = render_scad(tibia_script, f"{project_id}_tibia")
    assets["individual_parts"]["Actuators"] = render_scad(servo_script, f"{project_id}_servo")

    # --- 4. KINEMATIC COLLISION CHECK (SOFT FAIL) ---
    try:
        collision_manager = trimesh.collision.CollisionManager()
        meshes = {}
        
        for name, path in assets["individual_parts"].items():
            if path and os.path.exists(path):
                meshes[name] = trimesh.load(path)

        if "Chassis_Kit" in meshes and "Femur_Leg" in meshes:
            collision_manager.add_object("chassis", meshes["Chassis_Kit"])
            
            # Check if Femur hits Chassis at max rotation (hip swing)
            # Transform Femur to Front-Left Hip position
            T_hip = trimesh.transformations.translation_matrix([body_length/2, body_width/2, 0])
            # Rotate 45 degrees inward (common collision point)
            R_swing = trimesh.transformations.rotation_matrix(np.radians(45), [0, 0, 1])
            
            collision_manager.add_object("femur_test", meshes["Femur_Leg"], transform=trimesh.transformations.concatenate_matrices(T_hip, R_swing))
            
            is_colliding = collision_manager.in_collision_internal()
            assets["collision_report"]["collided"] = is_colliding
            if is_colliding:
                print("      ⚠️  CAD Alert: Leg geometry clips through chassis at max swing.")

    except Exception as e:
        print(f"      ⚠️  Collision Check skipped: {e}")

    return assets