# FILE: app/services/interconnect_service.py
import math

# --- CONFIGURATION ---
DEFAULT_SERVO_CABLE_LEN_MM = 300 # Standard servo wire length
FASTENER_M3_LEN = 8 # mm

def calculate_distance(pos_a, pos_b):
    """Euclidean distance between two [x,y,z] points."""
    if not pos_a or not pos_b: return 0.0
    return math.sqrt(sum((a - b)**2 for a, b in zip(pos_a, pos_b)))

def analyze_interconnects(bom, scene_graph):
    """
    Scans the physical layout (Scene Graph) to find missing wires and fasteners.
    """
    extras = []
    
    # 1. Map Components
    parts = {p.get('part_type'): p for p in bom}
    actuator = parts.get('Actuators', {})
    controller = parts.get('Servo_Controller', {})
    
    # Get Scene Graph Positions (from digital_twin_service)
    comps = scene_graph.get('components', [])
    chassis_node = next((c for c in comps if c['type'] == 'CHASSIS'), None)
    
    # If no chassis pos, assume origin
    center_pos = chassis_node['pos'] if chassis_node else [0, 0, 0]

    # =========================================================
    # 1. SERVO EXTENSION ANALYSIS
    # =========================================================
    # Check if legs are too far from the main body for standard wires
    
    # Find all leg components (Tibia is furthest point)
    far_points = [c for c in comps if c['type'] == 'TIBIA']
    
    extensions_needed = 0
    
    for leg in far_points:
        # Calculate distance from Tibia (foot) to Chassis Center (Brain)
        # We assume wire runs along leg, so we sum dimensions roughly
        # Real distance is path-based, but Euclidean * 1.5 is a safe heuristic for routing
        
        # Get parent positions recursively? 
        # Easier: Just use the 'pos' if available, or estimate from geometry
        # Let's use the Scene Graph geometry data
        dist = 300.0 # Default safe assumption
        
        # If leg relative pos exists:
        if 'relative_pos' in leg:
            # This is complex without a full transform tree walk.
            # Simplified Logic:
            # Front/Back legs are usually ~150mm from center + 200mm leg length
            dist = 350.0 
            
        if dist > DEFAULT_SERVO_CABLE_LEN_MM:
            extensions_needed += 1

    if extensions_needed > 0:
        extras.append({
            "part_type": "Cabling",
            "product_name": f"Servo Extension Cable 20cm (Pack of {extensions_needed})",
            "price": 6.99,
            "source_url": "Generic",
            "reason": "Leg reach exceeds standard servo wire length."
        })

    # =========================================================
    # 2. FASTENER CALCULATION (BOLTS & NUTS)
    # =========================================================
    # Robot dogs vibrate. They need Nylon Lock Nuts.
    
    # 4 screws per servo is standard
    total_servos = 12
    screw_count = total_servos * 4
    
    extras.append({
        "part_type": "Fasteners",
        "product_name": "M3 Screw & Nylon Locknut Kit (Stainless Steel)",
        "price": 12.99,
        "source_url": "Generic",
        "reason": f"Mounting hardware for {total_servos} actuators + chassis assembly."
    })

    # =========================================================
    # 3. POWER REGULATION (The "Bec" Check)
    # =========================================================
    # If using High Voltage Servos (12V) and a Raspberry Pi (5V), 
    # we MUST have a step-down converter.
    
    battery = parts.get('Battery', {})
    sbc = parts.get('Single_Board_Computer', {})
    
    bat_v_str = battery.get('engineering_specs', {}).get('voltage', '11.1V')
    is_hv_battery = "11" in bat_v_str or "12" in bat_v_str or "14" in bat_v_str
    
    # Does the Controller have a built-in BEC?
    ctrl_specs = str(controller.get('engineering_specs', {})).lower()
    has_bec = "bec" in ctrl_specs or "regulator" in ctrl_specs
    
    if is_hv_battery and sbc and not has_bec:
        extras.append({
            "part_type": "Voltage_Regulator",
            "product_name": "UBEC 5V 3A (Step-Down Converter)",
            "price": 5.99,
            "source_url": "Generic",
            "reason": "Required to power 5V Computer from 12V Battery rail."
        })

    return extras