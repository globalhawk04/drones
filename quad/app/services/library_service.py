# FILE: app/services/library_service.py
import re
from typing import Optional

# --- KNOWLEDGE BASE: ACTUATORS ---
# Mapping common servo model prefixes to their typical Torque (kg/cm) and Protocol.
STANDARD_SERVO_PATTERNS = {
    # --- MICRO / HOBBY (PWM) ---
    "SG90":  {"torque": 1.6, "type": "PWM", "class": "Micro", "voltage": "4.8-6V"},
    "MG90S": {"torque": 2.2, "type": "PWM", "class": "Micro", "voltage": "4.8-6V"},
    "MG996": {"torque": 11.0, "type": "PWM", "class": "Standard", "voltage": "4.8-7.2V"},
    "MG995": {"torque": 10.0, "type": "PWM", "class": "Standard", "voltage": "4.8-7.2V"},
    
    # --- ROBOTICS SERIAL BUS (ENTRY) ---
    # These are critical for "Spot-Micro" style robots
    "LX-16A":  {"torque": 17.0, "type": "Serial", "class": "Standard", "voltage": "6-8.4V"},
    "LX-224":  {"torque": 20.0, "type": "Serial", "class": "Standard", "voltage": "6-8.4V"},
    "SCS15":   {"torque": 15.0, "type": "Serial", "class": "Standard", "voltage": "6-8.4V"},
    "STS3215": {"torque": 19.0, "type": "Serial", "class": "Standard", "voltage": "6-7.4V"},
    
    # --- HIGH END / INDUSTRIAL (DYNAMIXEL & CLONES) ---
    # Required for the "Feed Mule" mission
    "XL430":   {"torque": 15.0, "type": "Dynamixel", "class": "Standard", "voltage": "11.1V"},
    "XM430":   {"torque": 40.0, "type": "Dynamixel", "class": "Standard", "voltage": "11.1-14.8V"},
    "MX-64":   {"torque": 64.0, "type": "Dynamixel", "class": "Large", "voltage": "11.1-14.8V"},
    "HTS-35H": {"torque": 35.0, "type": "Serial", "class": "Standard", "voltage": "9-12V"},
    "H54-200": {"torque": 200.0, "type": "Brushless", "class": "Giant", "voltage": "24V"}
}

def infer_actuator_specs(product_title: str) -> dict:
    """
    Analyzes a product title to guess torque, protocol, and voltage.
    Useful when the Vision AI misses specific fields or for 'sanity checking' the AI.
    """
    if not product_title:
        return {}
        
    title_lower = product_title.lower()
    specs = {}

    # 1. DATABASE LOOKUP: Check for known model numbers
    for model, data in STANDARD_SERVO_PATTERNS.items():
        if model.lower() in title_lower:
            specs["est_torque_kgcm"] = data["torque"]
            specs["protocol"] = data["type"]
            specs["size_class"] = data["class"]
            specs["voltage_rating"] = data["voltage"]
            break # Found a match, stop looking

    # 2. REGEX EXTRACTION: Look for "20kg", "35kg", etc.
    # Pattern matches "20kg", "20 kg", "20kg.cm", "20kg/cm"
    if "est_torque_kgcm" not in specs:
        torque_match = re.search(r"\b(\d{1,3}(?:\.\d)?)\s?(?:kg|kg\.cm|kg\/cm)\b", title_lower)
        if torque_match:
            specs["est_torque_kgcm"] = float(torque_match.group(1))

    # 3. PROTOCOL INFERENCE
    if "protocol" not in specs:
        if any(x in title_lower for x in ["serial", "bus", "uart", "smart servo", "feedback", "daisy chain"]):
            specs["protocol"] = "Serial"
        elif any(x in title_lower for x in ["pwm", "rc servo", "analog", "digital servo"]):
            # Note: "Digital Servo" usually means high-refresh PWM, not Serial Bus
            specs["protocol"] = "PWM"

    # 4. VOLTAGE INFERENCE
    if "voltage_rating" not in specs:
        if "hv" in title_lower or "high voltage" in title_lower:
            specs["voltage_rating"] = "7.4V+"
        elif "12v" in title_lower:
             specs["voltage_rating"] = "12V"

    return specs

def extract_chassis_size(product_title: str) -> Optional[float]:
    """
    Attempts to find the physical size of a chassis kit.
    Returns: Length in mm (approximate).
    """
    if not product_title: return None
    
    title_lower = product_title.lower()
    
    # Check for "250mm", "300mm", etc.
    match_mm = re.search(r"\b(\d{3})\s?mm\b", title_lower)
    if match_mm:
        return float(match_mm.group(1))
        
    # Check for standard Extrusion sizing (2020, 2040)
    # This implies a custom build, usually around 300-400mm scale
    if "2020" in title_lower or "extrusion" in title_lower:
        return 300.0 # Default assumption for 2020 robot dogs

    return None