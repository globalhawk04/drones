# FILE: main.py
import asyncio
import sys
import os
import json
import base64
import webbrowser
import random
import shutil
import subprocess
from datetime import datetime

# (Imports remain the same)
from app.services.ai_service import (
    analyze_user_requirements, refine_requirements, 
    generate_spec_sheet, generate_assembly_instructions,
    generate_assembly_blueprint, optimize_specs,
    ask_for_human_input 
)
from app.services.fusion_service import fuse_component_data
from app.services.physics_service import run_physics_simulation
from app.services.cad_service import generate_assets
from app.services.cost_service import generate_procurement_manifest
from app.services.schematic_service import generate_wiring_diagram
from app.services.geometry_sim_service import run_geometric_simulation

OUTPUT_DIR = os.path.abspath("output")
TEMPLATE_DIR = os.path.abspath("templates")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# (Helper functions remain the same)
def check_openscad():
    try:
        subprocess.run(["openscad", "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except: return False

def create_placeholder_stl(filepath):
    with open(filepath, "w") as f:
        f.write(f"solid placeholder\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 10 0 0\nvertex 0 10 0\nendloop\nendfacet\nendsolid placeholder")
    return filepath

def file_to_b64(path):
    if not path or not os.path.exists(path): return ""
    try:
        with open(path, "rb") as f: return f"data:model/stl;base64,{base64.b64encode(f.read()).decode('utf-8')}"
    except: return ""

def generate_flight_log(report):
    twr = report.get('twr', 1.0)
    hover = report.get('hover_throttle_percent', 50) / 100.0
    times, heights, throttles = [], [], []
    h = 0
    for i in range(100):
        times.append(i/10.0)
        err = 1.5 - h
        th = hover + (err * 0.5) if twr > 1.0 else 1.0
        th = max(0, min(1, th + (random.random()-0.5)*0.05))
        h += (th - hover) * 2.0 if twr > 1.0 else -0.5
        if h < 0: h = 0
        heights.append(round(h, 2)); throttles.append(round(th, 2))
    return {"time": times, "height": heights, "throttle_avg": throttles}


async def run():
    print("\n🚀 OPENFORGE SYSTEM ONLINE")
    print("==========================")

    # ... (Master Record Initialization and Intake/Clarification are unchanged) ...
    master_record = {
        "session_id": f"OF-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "initial_prompt": "", "clarification_log": [], "engineering_plan": {},
        "sourcing_log": [], "validation_log": [], "final_bom": [],
        "final_blueprint": {}, "final_simulations": {}, "final_cost": {}
    }

    if not check_openscad(): print("⚠️  OpenSCAD not found. Using placeholders.")
    
    prompt = input("\n👨‍✈️  Enter Mission Requirements > ")
    master_record["initial_prompt"] = prompt
    if not prompt: return
    
    analysis = await analyze_user_requirements(prompt)
    if not analysis: return

    qs = analysis.get("missing_critical_info", []) or analysis.get("clarifying_questions", [])
    if qs:
        print(f"\n🎤 Clarification needed ({len(qs)} questions):")
        for q in qs:
            answer = input(f'   {q} > ')
            master_record["clarification_log"].append({"question": q, "answer": answer})

    plan_answers = [log.get("answer", "") for log in master_record["clarification_log"]]
    plan = await refine_requirements(analysis, plan_answers)
    master_record["engineering_plan"] = plan
    print(f"\n✅ Plan Approved: {plan.get('build_summary')}")

    # --- Sourcing is now part of the main validation loop ---
    
    max_validation_attempts = 5 # Increased attempts for re-architecture
    validated_blueprint = None
    validated_bom = [] # Start with an empty BOM
    final_assets = {}
    current_specs = await generate_spec_sheet(plan) # Get initial specs

    for attempt in range(max_validation_attempts):
        print(f"\n>>>>> DESIGN VALIDATION ATTEMPT {attempt + 1} of {max_validation_attempts} <<<<<")
        
        # --- If BOM is empty, we need to perform initial sourcing ---
        if not validated_bom:
            print("\n🔎 Performing Initial Component Sourcing...")
            buy_list = current_specs.get('buy_list', [])
            temp_bom = []
            sourcing_ok = True
            for item in buy_list:
                part = await fuse_component_data(item['part_type'], item['search_query'])
                if part:
                    temp_bom.append(part)
                else:
                    print(f"     ⚠️  Initial sourcing failed for {item['part_type']}. Triggering re-architecture.")
                    sourcing_ok = False
                    break 
            if sourcing_ok:
                validated_bom = temp_bom
            else:
                # If initial sourcing fails, immediately trigger a redesign
                failure_report = {"type": "sourcing", "details": "Initial component sourcing failed. The entire BOM is suspect."}
                fix = await optimize_specs(validated_bom, failure_report)
                if fix and fix.get("replacements"):
                    # Discard everything and re-spec based on the AI's new anchor part query
                    anchor_part_query = fix["replacements"][0]
                    print(f"   -> Re-architecting BOM around new anchor: {anchor_part_query['part_type']}")
                    plan['forced_anchor'] = anchor_part_query # Inject the fix into the plan
                    current_specs = await generate_spec_sheet(plan)
                validated_bom = [] # Ensure BOM is empty to re-trigger sourcing
                continue

        validation_entry = {"attempt": attempt + 1, "bom_snapshot": [p.get('product_name', 'N/A') for p in validated_bom]}

        blueprint = await generate_assembly_blueprint(validated_bom)
        if not blueprint or not blueprint.get("is_buildable"):
            failure_reason = blueprint.get("incompatibility_reason", "AI failed to generate a valid blueprint.")
            failure_report = {"type": "conceptual", "details": failure_reason}
            validation_entry["failure"] = failure_report
            fix = await optimize_specs(validated_bom, failure_report)
            validation_entry["ai_fix_suggestion"] = fix
            master_record["validation_log"].append(validation_entry)
            
            # --- NUKE AND REBUILD LOGIC ---
            if "fundamentally invalid" in fix.get("diagnosis", "") or "critically incomplete" in fix.get("diagnosis", ""):
                print("   -> Diagnosis: BOM is fundamentally flawed. Re-architecting...")
                anchor_part = fix["replacements"][0]
                plan['forced_anchor'] = anchor_part
                current_specs = await generate_spec_sheet(plan)
                validated_bom = [] # NUKE: Reset the BOM
            else: # Simple part replacement
                replacement = fix["replacements"][0]
                new_part = await fuse_component_data(replacement['part_type'], replacement['new_search_query'])
                for i_bom, p_bom in enumerate(validated_bom):
                    if p_bom['part_type'] == replacement['part_type']: validated_bom[i_bom] = new_part; break
            continue # Restart the loop

        assets = generate_assets("mission", blueprint, validated_bom)
        geo_report = run_geometric_simulation(assets['calculated_specs'])

        if geo_report['status'] == 'FAIL':
            # Geometric failures are always single-part replacements
            failure_report = {"type": "geometric", "details": geo_report['errors']}
            validation_entry["failure"] = failure_report
            fix = await optimize_specs(validated_bom, failure_report)
            validation_entry["ai_fix_suggestion"] = fix
            master_record["validation_log"].append(validation_entry)
            
            replacement = fix["replacements"][0]
            new_part = await fuse_component_data(replacement['part_type'], replacement['new_search_query'])
            for i_bom, p_bom in enumerate(validated_bom):
                if p_bom['part_type'] == replacement['part_type']: validated_bom[i_bom] = new_part; break
            continue
        
        print("\n✅ DESIGN VALIDATED! All conceptual and geometric checks passed.")
        validation_entry["result"] = "SUCCESS"
        master_record["validation_log"].append(validation_entry)
        validated_blueprint = blueprint
        final_assets = assets
        break

    # ... (Finalization, Rendering, and Master Record saving logic remains the same) ...
    if not validated_blueprint:
        print(f"\n❌ FAILED TO VALIDATE DESIGN after {max_validation_attempts} attempts.")
        with open(os.path.join(OUTPUT_DIR, "master_record.json"), "w") as f: json.dump(master_record, f, indent=2)
        return

    master_record["final_bom"] = validated_bom
    master_record["final_blueprint"] = validated_blueprint
    
    print("\n📝 Finalizing Documentation and Simulations...")
    
    phys = run_physics_simulation(validated_bom)
    flight_log = generate_flight_log(phys)
    master_record["final_simulations"]["flight_physics"] = phys
    master_record["final_simulations"]["flight_log"] = flight_log

    guide = await generate_assembly_instructions(validated_blueprint)
    cost = generate_procurement_manifest(validated_bom)
    master_record["final_cost"] = cost
    
    with open(os.path.join(TEMPLATE_DIR, "dashboard.html"), "r") as f: html = f.read()
    
    individual_parts = final_assets.get("individual_parts", {})
    for part_name, part_path in individual_parts.items():
        if not part_path or not os.path.exists(part_path):
             placeholder_path = os.path.join(OUTPUT_DIR, f"mission_placeholder_{part_name}.stl")
             individual_parts[part_name] = create_placeholder_stl(placeholder_path)

    html = html.replace('"[[FRAME_B64]]"', f'"{file_to_b64(individual_parts.get("frame"))}"')
    html = html.replace('"[[MOTOR_B64]]"', f'"{file_to_b64(individual_parts.get("motor"))}"')
    html = html.replace('"[[FC_B64]]"', f'"{file_to_b64(individual_parts.get("fc"))}"')
    html = html.replace('"[[PROP_B64]]"', f'"{file_to_b64(individual_parts.get("prop"))}"')
    html = html.replace('"[[BATTERY_B64]]"', f'"{file_to_b64(individual_parts.get("battery"))}"')
    html = html.replace('"[[CAMERA_B64]]"', f'"{file_to_b64(individual_parts.get("camera"))}"')
    
    wheelbase = final_assets.get("calculated_specs", {}).get("wheelbase", 200)
    html = html.replace('[[WHEELBASE]]', str(wheelbase))
    
    html = html.replace('[[STEPS_JSON]]', json.dumps(guide.get("steps", [])))
    html = html.replace('[[PHYSICS_JSON]]', json.dumps(phys))
    html = html.replace('[[COST_JSON]]', json.dumps(cost))
    html = html.replace('[[FLIGHT_LOG_JSON]]', json.dumps(flight_log))
    
    out_path = os.path.join(OUTPUT_DIR, "dashboard.html")
    with open(out_path, "w") as f: f.write(html)
    
    with open(os.path.join(OUTPUT_DIR, "master_record.json"), "w") as f:
        json.dump(master_record, f, indent=2)

    print(f"\n🚀 Done. Dashboard: {out_path}")
    webbrowser.open(f"file://{out_path}")

if __name__ == "__main__":
    asyncio.run(run())