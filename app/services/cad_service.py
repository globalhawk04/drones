# FILE: app/services/cad_service.py
import os
import subprocess
import logging

# Assume a simple helper function exists to find parts in the BOM
def find_part_in_bom(bom, part_type_query):
    """Finds the first item in a BOM that matches the part_type_query."""
    for item in bom:
        if part_type_query.lower() in item.get("part_type", "").lower():
            return item
    return None

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
SCAD_LIB_PATH = os.path.join(PROJECT_ROOT, "cad", "library.scad")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def render_scad(script: str, output_filename: str) -> str | None:
    """
    Writes SCAD script to file and uses OpenSCAD to compile it to STL.
    """
    scad_path = os.path.join(OUTPUT_DIR, f"{output_filename}.scad")
    stl_path = os.path.join(OUTPUT_DIR, f"{output_filename}.stl")
    
    with open(scad_path, "w") as f:
        f.write(script)
    
    try:
        cmd = ["openscad", "-o", stl_path, scad_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if os.path.exists(stl_path):
            return stl_path
        return None
    except Exception as e:
        logger.error(f"❌ OpenSCAD Render Failed for {output_filename}: {e}")
        return None

def generate_assets(project_id: str, blueprint: dict, bom: list) -> dict:
    """
    Generates all CAD assets by executing a validated assembly blueprint.
    """
    print("--> 🏗️  CAD Service: Executing blueprint to generate digital twin...")
    assets = {"individual_parts": {}, "assembly_files": {}}
    
    # --- 1. EXTRACT PRECISE SPECS FROM BOM ---
    frame_part = find_part_in_bom(bom, "frame") or {}
    motor_part = find_part_in_bom(bom, "motor") or {}
    prop_part = find_part_in_bom(bom, "prop") or {}
    fc_part = find_part_in_bom(bom, "fc") or {}
    cam_part = find_part_in_bom(bom, "camera") or {}
    bat_part = find_part_in_bom(bom, "battery") or {}

    # --- FIX: Implement robust `None` checking for all values from engineering_specs ---
    def get_spec(part, key, default):
        val = part.get("engineering_specs", {}).get(key)
        return val if val is not None else default

    wheelbase = float(get_spec(frame_part, "wheelbase_mm", 225.0))
    prop_diam_mm = float(get_spec(prop_part, "diameter_mm", 127.0))
    motor_mount_mm = float(get_spec(motor_part, "mounting_mm", 16.0))
    fc_mount_mm = float(get_spec(fc_part, "mounting_mm", 30.5))
    cam_width_mm = float(get_spec(cam_part, "width_mm", 19.0))
    
    motor_stator_size = int(get_spec(motor_part, "stator_size", 2207))
    battery_cells = int(get_spec(bat_part, "cells", 6))
    battery_capacity = int(get_spec(bat_part, "capacity_mah", 1300))
    is_digital = "true" if cam_width_mm > 19 else "false"
    
    assets["calculated_specs"] = {
        "wheelbase": wheelbase,
        "prop_diameter_mm": prop_diam_mm,
        "fc_mounting_mm": fc_mount_mm,
    }
    
    # --- 2. GENERATE INDIVIDUAL COMPONENT STLs ---
    print("    -> Generating individual component models...")
    assets["individual_parts"]["frame"] = render_scad(f'use <{SCAD_LIB_PATH}>; pro_frame({wheelbase});', f"{project_id}_frame")
    assets["individual_parts"]["motor"] = render_scad(f'use <{SCAD_LIB_PATH}>; pro_motor({motor_stator_size});', f"{project_id}_motor")
    assets["individual_parts"]["prop"] = render_scad(f'use <{SCAD_LIB_PATH}>; pro_prop({prop_diam_mm / 25.4});', f"{project_id}_prop")
    assets["individual_parts"]["fc"] = render_scad(f'use <{SCAD_LIB_PATH}>; pro_stack({fc_mount_mm}, {is_digital});', f"{project_id}_fc")
    assets["individual_parts"]["camera"] = render_scad(f'use <{SCAD_LIB_PATH}>; pro_camera({cam_width_mm});', f"{project_id}_camera")
    assets["individual_parts"]["battery"] = render_scad(f'use <{SCAD_LIB_PATH}>; pro_battery({battery_cells}, {battery_capacity});', f"{project_id}_battery")
    
    # --- 3. BUILD THE BLUEPRINT-DRIVEN ASSEMBLY SCRIPT ---
    print("    -> Assembling digital twin based on blueprint steps...")
    assembly_script_lines = [
        f'// Assembly for Project: {project_id}', f'$fn=50;\n'
    ]
    
    # Generate temporary .scad files for each part to be included
    for part_name, stl_path in assets["individual_parts"].items():
        if stl_path:
            scad_include_path = os.path.join(OUTPUT_DIR, f"{project_id}_{part_name}.scad")
            with open(scad_include_path, "w") as f:
                f.write(f'import("{stl_path}");')

    # Always start with the frame at the origin
    assembly_script_lines.append(f'include <{os.path.join(OUTPUT_DIR, f"{project_id}_frame.scad")}>;')
    offset = (wheelbase / 2) * 0.7071

    for step in blueprint.get("blueprint_steps", []):
        action = step.get("action")
        
        if action == "MOUNT_MOTORS":
            assembly_script_lines.append("\n// Step: Mount Motors")
            assembly_script_lines.append(f'translate([{offset}, {offset}, 5]) include <{os.path.join(OUTPUT_DIR, f"{project_id}_motor.scad")}>;')
            assembly_script_lines.append(f'translate([-{offset}, {offset}, 5]) include <{os.path.join(OUTPUT_DIR, f"{project_id}_motor.scad")}>;')
            assembly_script_lines.append(f'translate([-{offset}, -{offset}, 5]) include <{os.path.join(OUTPUT_DIR, f"{project_id}_motor.scad")}>;')
            assembly_script_lines.append(f'translate([{offset}, -{offset}, 5]) include <{os.path.join(OUTPUT_DIR, f"{project_id}_motor.scad")}>;')

        elif action == "INSTALL_STACK":
            assembly_script_lines.append("\n// Step: Install FC Stack")
            assembly_script_lines.append(f'translate([0, 0, 8]) include <{os.path.join(OUTPUT_DIR, f"{project_id}_fc.scad")}>;')

        elif action == "SECURE_CAMERA":
            assembly_script_lines.append("\n// Step: Secure Camera")
            assembly_script_lines.append(f'translate([0, 35, 10]) include <{os.path.join(OUTPUT_DIR, f"{project_id}_camera.scad")}>;')
            
        elif action == "ATTACH_PROPS":
            assembly_script_lines.append("\n// Step: Attach Propellers")
            assembly_script_lines.append(f'translate([{offset}, {offset}, 15]) include <{os.path.join(OUTPUT_DIR, f"{project_id}_prop.scad")}>;')
            assembly_script_lines.append(f'translate([-{offset}, {offset}, 15]) rotate([0,0,180]) include <{os.path.join(OUTPUT_DIR, f"{project_id}_prop.scad")}>;')
            assembly_script_lines.append(f'translate([-{offset}, -{offset}, 15]) include <{os.path.join(OUTPUT_DIR, f"{project_id}_prop.scad")}>;')
            assembly_script_lines.append(f'translate([{offset}, -{offset}, 15]) rotate([0,0,180]) include <{os.path.join(OUTPUT_DIR, f"{project_id}_prop.scad")}>;')
            
        elif action == "MOUNT_BATTERY":
            assembly_script_lines.append("\n// Step: Mount Battery")
            assembly_script_lines.append(f'translate([0, 0, -20]) include <{os.path.join(OUTPUT_DIR, f"{project_id}_battery.scad")}>;')

    # --- 4. RENDER AND SAVE THE FINAL ASSEMBLY ---
    full_assembly_script = "\n".join(assembly_script_lines)
    assets["assembly_files"]["scad"] = os.path.join(OUTPUT_DIR, f"{project_id}_assembly.scad")
    with open(assets["assembly_files"]["scad"], "w") as f:
        f.write(full_assembly_script)
        
    print("    -> Rendering final assembled model...")
    # For web visualization, we don't need to render the full assembly STL, which can be slow.
    # The individual STLs are enough. This line can be optionally enabled for debugging.
    # assets["assembly_files"]["stl"] = render_scad(full_assembly_script, f"{project_id}_assembly")

    print("   ✅ CAD generation complete.")
    return assets