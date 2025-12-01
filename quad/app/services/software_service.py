# FILE: app/services/software_service.py
from app.services.ai_service import call_llm_for_json
from app.prompts import SOFTWARE_ARCHITECT_INSTRUCTION
import json

async def design_compute_stack(mission_profile, bom):
    """
    Architects the Software Stack (OS, Middleware, Drivers) based on hardware and mission.
    """
    print("--> 🧠 Software Architect: Designing the Robotics Middleware...")
    
    # 1. Identify Hardware Compute Class
    parts = {p.get('part_type'): p for p in bom}
    sbc = parts.get('Single_Board_Computer', {})
    controller = parts.get('Servo_Controller', {})
    
    sbc_name = sbc.get('product_name', '').lower()
    ctrl_name = controller.get('product_name', '').lower()
    
    # 2. Heuristic: Detect Architecture Type
    arch_type = "UNKNOWN"
    if "jetson" in sbc_name or "orin" in sbc_name:
        arch_type = "AI_EDGE"
    elif "raspberry pi" in sbc_name or "rpi" in sbc_name:
        arch_type = "STANDARD_ROS"
    elif "esp32" in sbc_name or "arduino" in sbc_name or "teensy" in sbc_name:
        arch_type = "MICROCONTROLLER_ONLY"
    
    # 3. AI Design Step
    # We feed the hardware context to the AI to get specific package recommendations
    context = {
        "mission": mission_profile,
        "hardware_detected": {
            "sbc": sbc_name,
            "controller": ctrl_name,
            "architecture_class": arch_type
        }
    }
    
    software_plan = await call_llm_for_json(
        f"CONTEXT: {json.dumps(context)}", 
        SOFTWARE_ARCHITECT_INSTRUCTION
    )
    
    if not software_plan:
        # Fallback Plan if AI fails
        software_plan = {
            "operating_system": "Ubuntu 22.04 LTS (Server)",
            "locomotion_framework": "Champ (ROS 2 Humble)",
            "microcontroller_bridge": "Micro-ROS Agent"
        }

    # 4. Hardware Dependency Check (The "Add-ons")
    # Software choices trigger hardware needs (e.g., cooling, wifi dongles)
    hardware_additions = []
    
    # Cooling Check
    if arch_type == "AI_EDGE":
        hardware_additions.append({
            "part_type": "Cooling",
            "search_query": f"Active cooling fan heatsink for {sbc_name}",
            "reason": "AI Edge Compute requires active thermal management."
        })
    
    # Telemetry Check
    if "patrol" in str(mission_profile).lower():
        hardware_additions.append({
            "part_type": "Telemetry",
            "search_query": "USB 4G LTE Modem Dongle Linux compatible",
            "reason": "Patrol mission implies long-range connectivity requirements."
        })

    # 5. Generate "Flash Image" Config
    # This simulates generating a cloud-init or docker-compose file
    deployment_manifest = {
        "base_image": software_plan.get("operating_system"),
        "containers": [
            {"name": "ros-core", "image": "ros:humble-ros-base"},
            {"name": "locomotion", "image": f"openforge/{software_plan.get('locomotion_framework', 'champ').lower()}:latest"},
            {"name": "hardware-interface", "env": {"SERIAL_PORT": "/dev/ttyUSB0"}}
        ]
    }

    return {
        "stack_design": software_plan,
        "deployment_manifest": deployment_manifest,
        "hardware_additions": hardware_additions
    }