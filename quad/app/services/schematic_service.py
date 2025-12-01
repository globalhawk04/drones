# FILE: app/services/schematic_service.py
import os
try:
    import graphviz
except ImportError:
    graphviz = None

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "static", "generated")

def generate_wiring_diagram(project_id: str, bom: list) -> str:
    """
    Generates a wiring schematic PNG for a Quadruped Robot.
    Visualizes Power Rails (HV vs 5V) and Data Buses (I2C/UART/USB).
    """
    if not graphviz:
        print("⚠️ Graphviz not installed. Skipping schematic.")
        return None

    # 1. Initialize Diagram
    dot = graphviz.Digraph(comment='Quadruped Wiring Diagram')
    dot.attr(rankdir='TB', bgcolor='#1a202c', fontcolor='white', splines='ortho')
    
    # --- STYLE DEFINITIONS ---
    node_attr = {
        'shape': 'box', 'style': 'filled', 'color': '#4a5568', 
        'fontcolor': 'white', 'fontname': 'Helvetica', 'margin': '0.2'
    }
    
    # Component Specific Styles
    bat_attr = node_attr.copy()
    bat_attr.update({'fillcolor': '#d69e2e', 'fontcolor': 'black', 'shape': 'component'})
    
    sbc_attr = node_attr.copy()
    sbc_attr.update({'fillcolor': '#2b6cb0', 'shape': 'note'}) # Blue (Brain)
    
    driver_attr = node_attr.copy()
    driver_attr.update({'fillcolor': '#2c7a7b', 'shape': 'box'}) # Teal (Spine)

    servo_attr = node_attr.copy()
    servo_attr.update({'shape': 'ellipse', 'fontsize': '10', 'width': '0.8'})

    # Edge Styles
    pwr_hv_attr = {'color': '#ecc94b', 'penwidth': '2.5'} # High Voltage (Yellow)
    pwr_5v_attr = {'color': '#f56565', 'penwidth': '1.5'} # 5V Logic (Red)
    data_attr = {'color': '#63b3ed', 'penwidth': '1.5', 'style': 'dashed'} # Data (Blue)

    # 2. Extract Key Components
    parts = {p.get('part_type'): p for p in bom}
    
    has_ubec = parts.get('Voltage_Regulator') is not None
    sbc_name = parts.get('Single_Board_Computer', {}).get('product_name', 'SBC')
    ctrl_name = parts.get('Servo_Controller', {}).get('product_name', 'Servo Driver')
    
    # 3. Build Power Core
    dot.node('BAT', 'LiPo Battery\n(2S-4S)', **bat_attr)
    
    # Branch A: Logic Power
    if has_ubec:
        dot.node('UBEC', 'UBEC / Regulator\n(Step-Down)', **node_attr)
        dot.edge('BAT', 'UBEC', label='V_BAT', **pwr_hv_attr)
        dot.edge('UBEC', 'SBC', label='5V / 3A', **pwr_5v_attr)
    else:
        # Assume Controller handles regulation or USB bank used
        dot.edge('BAT', 'SBC', label='V_BAT (Risk?)', **pwr_hv_attr)

    # Branch B: Servo Power
    dot.node('DRIVER', f'Servo Controller\n"{ctrl_name}"', **driver_attr)
    dot.edge('BAT', 'DRIVER', label='High Current Rail', **pwr_hv_attr)

    # 4. Build The Brain (SBC)
    dot.node('SBC', f'Computer\n"{sbc_name}"', **sbc_attr)
    
    # Connection Brain -> Spine
    dot.edge('SBC', 'DRIVER', label='I2C / USB / UART', **data_attr)

    # 5. Build Sensors
    if parts.get('Lidar_Module'):
        dot.node('LIDAR', 'Lidar Scanner', **node_attr)
        dot.edge('SBC', 'LIDAR', label='USB / UART', **data_attr)
        dot.edge('UBEC', 'LIDAR', label='5V', **pwr_5v_attr) # Usually needs power

    if parts.get('Depth_Camera'):
        dot.node('CAM', 'Depth Camera\n(OAK-D / RealSense)', **node_attr)
        dot.edge('SBC', 'CAM', label='USB 3.0', **data_attr)

    # 6. Build Legs (The Servo Clusters)
    # Grouping servos makes the diagram readable
    
    legs = ["FL", "FR", "RL", "RR"]
    joints = ["Hip", "Upper", "Lower"]
    
    # Determine Protocol (Serial vs PWM) to label wires
    actuator = parts.get('Actuators', {})
    is_serial = "serial" in actuator.get('engineering_specs', {}).get('protocol', 'pwm').lower()
    
    wire_label = "Daisy Chain" if is_serial else "PWM"
    
    with dot.subgraph(name='cluster_legs') as c:
        c.attr(label='Actuation System', color='white', style='dashed')
        
        for leg in legs:
            with c.subgraph(name=f'cluster_{leg}') as l:
                l.attr(label=f'{leg} Leg', color='#4a5568')
                
                prev_node = 'DRIVER'
                
                for joint in joints:
                    node_id = f"{leg}_{joint}"
                    l.node(node_id, f"{joint}\nServo", **servo_attr)
                    
                    if is_serial:
                        # Serial: Driver -> Hip -> Upper -> Lower
                        if joint == "Hip":
                            dot.edge('DRIVER', node_id, color='#ecc94b')
                        else:
                            # Link to previous servo in chain
                            prev_joint_idx = joints.index(joint) - 1
                            prev_id = f"{leg}_{joints[prev_joint_idx]}"
                            dot.edge(prev_id, node_id, color='#ecc94b')
                    else:
                        # PWM: Driver -> Each Servo Individually
                        dot.edge('DRIVER', node_id, **data_attr) # Signal
                        # Note: We omit V+ lines for PWM to keep graph clean, implying 3-wire cable

    # 7. Render
    output_path_base = os.path.join(OUTPUT_DIR, f"{project_id}_schematic")
    try:
        final_path = dot.render(filename=output_path_base, format='png', cleanup=True)
        print(f"⚡ Robotic Schematic Generated: {final_path}")
        return final_path
    except Exception as e:
        print(f"❌ Graphviz Error: {e}")
        return None