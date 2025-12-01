# FILE: app/services/optimizer.py
import copy
import re

class EngineeringOptimizer:
    """
    The 'Brain' of the operation.
    Analyzes Physics/Simulation reports and suggests hardware changes.
    Updated for QUADRUPED ROBOTICS.
    """
    
    def analyze_and_fix(self, current_bom, physics_report, simulation_report=None):
        """
        Input: Current BOM + Physics Service Report
        Output: New BOM Requests (Fixes)
        """
        fixes = []
        
        # Extract Data
        # Physics Report comes from app.services.physics_service
        torque_stats = physics_report.get('torque_physics', {})
        safety_margin = torque_stats.get('safety_margin', 0.0)
        
        viability = physics_report.get('viability', {})
        failure_mode = viability.get('failure_mode')

        print(f"\n🧠 [AI ENGINEER] Optimizing Design. Safety Margin: {safety_margin:.2f}x")
        
        # --- HEURISTIC 1: TORQUE INSUFFICIENCY (The "Weak Knees" Problem) ---
        # Robot cannot stand up or burns out servos.
        if safety_margin < 1.5:
            severity = "CRITICAL" if safety_margin < 1.0 else "WARNING"
            
            # Strategy A: Throw money at it (Stronger Servos)
            current_actuator = self._find_part(current_bom, 'Actuators')
            current_torque = self._get_spec(current_actuator, 'est_torque_kgcm')
            
            target_torque = current_torque * 1.5
            
            fixes.append({
                "type": "UPGRADE_PART",
                "severity": severity,
                "part_type": "Actuators",
                "diagnosis": f"Insufficient Torque ({safety_margin:.2f}x margin). Legs will collapse.",
                "action": f"Sourcing stronger servos (> {int(target_torque)}kg).",
                "search_modifier": f"{int(target_torque)}kg serial bus servo"
            })
            
            # Strategy B: Change Geometry (Shorten Legs for Leverage)
            # Torque = Force * Distance. Reducing distance reduces torque load.
            fixes.append({
                "type": "MODIFY_GEOMETRY",
                "severity": "ADVISORY",
                "diagnosis": "Legs are too long for these servos.",
                "action": "Shortening Femur length by 15% to increase mechanical advantage.",
                "param_change": {"femur_length_mm": 0.85}
            })

        # --- HEURISTIC 2: VOLTAGE / BROWNOUT ---
        # Did we calculate a brownout risk in compatibility_service?
        # (We assume compatibility check data might be passed here or re-evaluated)
        
        # Heuristic: Check if payload is negative (Physics service calculation)
        est_payload = torque_stats.get('est_payload_capacity_kg', 0)
        if est_payload < 0.2: # Less than 200g payload capacity is useless for a rancher
            fixes.append({
                "type": "WEIGHT_REDUCTION",
                "severity": "WARNING",
                "diagnosis": "Robot has zero useful payload capacity.",
                "action": "Switching to Carbon Fiber or smaller Battery to save weight.",
                "search_modifier": "Carbon fiber quadruped chassis kit"
            })

        # --- HEURISTIC 3: BATTERY SAG ---
        # If runtime is abysmal
        runtime = physics_report.get('meta', {}).get('est_runtime_min', 0)
        if runtime < 15.0:
            fixes.append({
                "type": "UPGRADE_PART",
                "severity": "WARNING",
                "part_type": "Battery",
                "diagnosis": f"Runtime is only {runtime} min. Rancher needs > 30 min.",
                "action": "Finding higher capacity LiPo (high density).",
                "search_modifier": "Li-Ion 21700 pack 3S" # Li-Ion has better energy density than LiPo
            })

        if not fixes:
            return None 

        return {
            "status": "NEEDS_REVISION",
            "optimization_plan": fixes
        }

    def _find_part(self, bom, part_type):
        return next((i for i in bom if part_type in i.get('part_type', '')), {})

    def _get_spec(self, part, key):
        return float(part.get('engineering_specs', {}).get(key, 0))