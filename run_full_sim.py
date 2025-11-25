import os
import shutil
import time

# Import our modules
from app.cad.assembly import DroneAssembler
from app.cad.exporter import URDFExporter
from app.sim.scenarios import FlightTestRunner

def main():
    print("\n" + "="*50)
    print("🚀 OPENFORGE: AUTONOMOUS DRONE COMPILER")
    print("="*50)
    
    # 1. DEFINE SPECS (Mocking the AI Phase)
    specs = {
        "name": "Interceptor_V1",
        "wheelbase_mm": 225,
        "motor_mount_mm": 16.0,
        "stack_mount_mm": 30.5,
        "arm_thickness_mm": 5.0,
        "prop_diameter_inch": 5.0
    }
    print(f"📋 SPECS: 5\" Freestyle Frame | {specs['wheelbase_mm']}mm Wheelbase")

    # 2. GENERATE CAD
    print("\n🏭 PHASE 1: FABRICATION (CAD ENGINE)")
    output_folder = "static/sim_build"
    
    # Clean up old run
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    
    try:
        assembler = DroneAssembler(specs)
        assembler.build() # Internal memory build
        
        exporter = URDFExporter(assembler)
        urdf_path = exporter.export(output_dir=output_folder)
        
        print(f"✅ Fabrication Complete.")
        print(f"   Files saved to: {output_folder}")
        
    except Exception as e:
        print(f"❌ CAD Error: {e}")
        return

    # 3. RUN SIMULATION
    print("\n🧪 PHASE 2: PHYSICS SIMULATION (PYBULLET)")
    print("   Initializing Test Environment...")
    
    try:
        # 1200g thrust per motor is typical for a 2207 motor on 4S
        runner = FlightTestRunner(urdf_path, max_thrust_g=1200.0, gui=True)
        
        # Run a 5-second hover test
        results = runner.run_hover_test(duration_sec=8.0, target_height=1.0)
        
        print("\n" + "="*30)
        print("🚩 FLIGHT TEST REPORT")
        print("="*30)
        print(f"Status: {results['status']}")
        print(f"Throttle: {results['hover_throttle_pct']}%")
        print("="*30)
        
        # Keep window open
        sim = results.get("sim_instance")
        if sim:
            print("\n👀 Simulation Paused for Inspection.")
            print("   Use Mouse to Rotate/Zoom.")
            print("   [CTRL+Click] to drag the drone.")
            input("   👉 PRESS ENTER TO CLOSE...")
            sim.close()
            
    except Exception as e:
        print(f"❌ Simulation Error: {e}")

if __name__ == "__main__":
    main()
