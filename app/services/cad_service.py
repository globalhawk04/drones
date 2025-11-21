# FILE: app/services/cad_service.py
import os
import subprocess
import logging

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
SCAD_LIB_PATH = os.path.join(PROJECT_ROOT, "cad", "library.scad")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "static", "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def render_scad(script: str, output_filename: str) -> str:
    """
    Writes SCAD script to file and uses OpenSCAD to compile it to STL.
    Returns the absolute path to the generated STL.
    """
    scad_path = os.path.join(OUTPUT_DIR, f"{output_filename}.scad")
    stl_path = os.path.join(OUTPUT_DIR, f"{output_filename}.stl")
    
    with open(scad_path, "w") as f:
        f.write(script)
    
    try:
        # Headless render using OpenSCAD
        cmd = ["openscad", "-o", stl_path, "--export-format", "binstl", scad_path]
        # Timeout set to 30s to prevent hangs
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if os.path.exists(stl_path):
            return stl_path
        return None
    except Exception as e:
        logger.error(f"❌ OpenSCAD Render Failed for {output_filename}: {e}")
        return None

def estimate_stator_from_mount(mount_mm):
    if mount_mm > 15: return 2207
    if mount_mm > 11: return 1404
    if mount_mm > 8: return 1103
    return 802

def generate_assets(project_id: str, specs: dict):
    """
    Generates High-Fidelity CAD assets for ALL components.
    """
    # --- 1. DIMENSION SOLVER ---
    prop_diam_mm = float(specs.get("prop_diameter_mm", 127))
    prop_diam_inch = prop_diam_mm / 25.4
    
    # Wheelbase Calculation
    min_side = prop_diam_mm + 10
    min_wheelbase = min_side * 1.414
    user_wheelbase = float(specs.get("wheelbase", 0))
    wheelbase = max(user_wheelbase, min_wheelbase)

    # Components
    mount_mm = float(specs.get("motor_mounting_mm", 16.0))
    stator_size = specs.get("motor_stator_size", estimate_stator_from_mount(mount_mm))
    fc_mount = float(specs.get("fc_mounting_mm", 30.5))
    cam_width = float(specs.get("camera_width_mm", 19.0))
    is_digital = "true" if cam_width >= 18 else "false"
    capacity = specs.get("battery_capacity", 1300)
    cells = specs.get("battery_cells", 6)

    assets = {
        "wheelbase": wheelbase,
        "calculated_specs": {
            "wheelbase": wheelbase,
            "prop_diam_mm": prop_diam_mm,
            "min_safe_gap": min_side - prop_diam_mm
        }
    }

    # --- 2. GENERATE INDIVIDUAL STLs (For Web Visualizer) ---
    
    # A. FRAME
    script_frame = f"""use <{SCAD_LIB_PATH}>; $fn=50;
    pro_frame(wheelbase={wheelbase}, arm_thick=4, plate_thick=2, stack_mounting={fc_mount});"""
    assets["frame"] = render_scad(script_frame, f"{project_id}_frame")

    # B. MOTOR (Single)
    script_motor = f"""use <{SCAD_LIB_PATH}>; $fn=50;
    pro_motor({stator_size}, 0);"""
    assets["motor"] = render_scad(script_motor, f"{project_id}_motor")

    # C. PROP (Single)
    script_prop = f"""use <{SCAD_LIB_PATH}>; $fn=50;
    pro_prop({prop_diam_inch}, 4.3, 3);"""
    assets["prop"] = render_scad(script_prop, f"{project_id}_prop")

    # D. FC STACK
    script_fc = f"""use <{SCAD_LIB_PATH}>; $fn=50;
    pro_stack({fc_mount}, {is_digital});"""
    assets["fc"] = render_scad(script_fc, f"{project_id}_fc")

    # E. CAMERA
    script_cam = f"""use <{SCAD_LIB_PATH}>; $fn=50;
    pro_camera({cam_width}, {is_digital});"""
    assets["camera"] = render_scad(script_cam, f"{project_id}_camera")

    # F. BATTERY
    script_bat = f"""use <{SCAD_LIB_PATH}>; $fn=50;
    pro_battery({cells}, {capacity});"""
    assets["battery"] = render_scad(script_bat, f"{project_id}_battery")

    # --- 3. GENERATE FULL ASSEMBLY SCAD (For Reference) ---
    offset = wheelbase / 2 * 0.7071;
    assembly_script = f"""
    use <{SCAD_LIB_PATH}>;
    $fn=30;
    pro_frame(wheelbase={wheelbase}, arm_thick=4, plate_thick=2, stack_mounting={fc_mount});
    translate([offset, offset, 0]) pro_motor({stator_size}, 0);
    translate([-offset, offset, 0]) pro_motor({stator_size}, 0);
    translate([-offset, -offset, 0]) pro_motor({stator_size}, 0);
    translate([offset, -offset, 0]) pro_motor({stator_size}, 0);
    translate([0,0,4]) pro_stack({fc_mount}, {is_digital});
    translate([0, -{fc_mount + 20}, 20]) pro_camera({cam_width}, {is_digital});
    translate([0, 0, 35]) pro_battery({cells}, {capacity});
    """
    assets["assembly_scad"] = os.path.join(OUTPUT_DIR, f"{project_id}_assembly.scad")
    with open(assets["assembly_scad"], "w") as f:
        f.write(assembly_script)

    return assets