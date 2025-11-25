import os
import shutil
import json
import time
from app.cad.assembly import DroneAssembler
from app.cad.exporter import URDFExporter
from app.sim.scenarios import FlightTestRunner
from app.services.optimizer import EngineeringOptimizer

MAX_ITERATIONS = 5

def main():
    print("\n" + "="*60)
    print("🤖 AUTO-ENGINEER: EVOLUTIONARY DESIGN LOOP")
    print("="*60)
    
    # 1. INTENT (The "Seed" Design)
    # Intentionally bad design: Heavy frame, small props.
    current_specs = {
        "name": "Prototype_V1",
        "wheelbase_mm": 225,
        "motor_mount_mm": 16.0,
        "stack_mount_mm": 30.5,
        "arm_thickness_mm": 6.0, # Very Heavy Arms
        "prop_diameter_inch": 4.0 # Too small for this frame size!
    }
    
    optimizer = EngineeringOptimizer()
    history = []
    
    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n🔄 GENERATION {iteration}: {current_specs['name']}")
        print(f"   🧬 DNA: Props={current_specs['prop_diameter_inch']}\" | Arms={current_specs['arm_thickness_mm']}mm")
        
        # --- PHASE 1: FABRICATION ---
        iter_folder = f"static/evolution/gen_{iteration}"
        if os.path.exists(iter_folder): shutil.rmtree(iter_folder)
        
        try:
            assembler = DroneAssembler(current_specs)
            assembler.build()
            exporter = URDFExporter(assembler)
            urdf_path = exporter.export(output_dir=iter_folder)
        except Exception as e:
            print(f"   ❌ Fabrication Error: {e}")
            break
            
        # --- PHASE 2: SIMULATION (The Exam) ---
        print("   🧪 Simulation: Running Acrobatic Flight Test...")
        # Note: We turn off GUI for the first few loops to speed it up (Headless Mode), 
        # only showing the final result. 
        # Change gui=True if you want to watch every failure.
        gui_mode = True 
        
        runner = FlightTestRunner(urdf_path, max_thrust_g=1000.0, gui=gui_mode)
        
        # We run a shorter test for the loop
        results = runner.run_acrobatic_show(duration_sec=12.0, video_filename=f"{iter_folder}/flight.mp4")
        
        # Close the sim instantly to move to next iteration
        if results.get("sim_instance"):
            results["sim_instance"].close()
            
        print(f"   📊 Result: {results['status']} (Hover: {results['hover_throttle_pct']}%)")
        
        # Save "Master Source of Truth" for this generation
        master_record = {
            "generation": iteration,
            "specs": current_specs,
            "performance": results,
            "timestamp": time.time()
        }
        with open(f"{iter_folder}/master_dna.json", "w") as f:
            json.dump(master_record, f, indent=2, default=str)
        
        history.append(master_record)

        # --- PHASE 3: EVOLUTION (The Decision) ---
        if results['status'] == "PASS" and results['hover_throttle_pct'] < 60:
            print(f"\n✅ DESIGN CONVERGED! {current_specs['name']} is optimal.")
            print(f"   🎥 Final Video: {iter_folder}/flight.mp4")
            break
        
        # Ask the Optimizer for a mutation
        optimization = optimizer.analyze_and_fix(current_specs, results)
        
        if not optimization:
            print("\n✅ Optimizer says no more changes needed.")
            break
            
        print(f"   🔧 OPTIMIZATION REQUIRED:")
        for note in optimization['reasoning']:
            print(f"      - {note}")
            
        # Apply Mutation
        current_specs = optimization['new_specs']
        
        if iteration == MAX_ITERATIONS:
            print("\n❌ MAX GENERATIONS REACHED. Solution not found.")

if __name__ == "__main__":
    main()