# FILE: app/services/ik_service.py
import math

class InverseKinematicsService:
    def __init__(self, femur_len=0.1, tibia_len=0.1):
        """
        Simple 2-DOF Planar IK Solver.
        Assumes the leg moves in a vertical plane (Forward/Back + Up/Down).
        
        Args:
            femur_len (float): Length of upper leg in meters.
            tibia_len (float): Length of lower leg in meters.
        """
        self.l1 = femur_len
        self.l2 = tibia_len

    def solve_2dof(self, target_x, target_z):
        """
        Calculates joint angles to reach a target (x, z) relative to the hip.
        
        Args:
            target_x (float): Forward distance from hip (meters).
            target_z (float): Vertical distance from hip (meters). Positive is DOWN in this logic.
        
        Returns:
            tuple: (hip_angle_rad, knee_angle_rad) or (None, None) if unreachable.
        """
        # Distance from hip to target foot position
        # We assume Z is negative in world space (down), but for triangle math we treat distance as positive magnitude
        r = math.sqrt(target_x**2 + target_z**2)
        
        # Reachability Check
        if r > (self.l1 + self.l2) or r == 0:
            return None, None # Target out of reach or singular

        # Law of Cosines
        # c^2 = a^2 + b^2 - 2ab*cos(C)
        # We want the angle at the knee (C)
        
        # Cosine of the internal knee angle
        cos_knee = (self.l1**2 + self.l2**2 - r**2) / (2 * self.l1 * self.l2)
        
        # Clamp for floating point errors
        cos_knee = max(-1.0, min(1.0, cos_knee))
        
        # Internal angles
        alpha_knee = math.acos(cos_knee) # Angle inside the triangle at knee
        
        # The actual servo angle usually measures deviation from straight or right angle
        # In our USD, Knee 0 is straight, -angle bends backward.
        # If leg is straight, angle is 0. If bent 90 deg, angle is -90.
        # Geometry: Internal angle is 180 (PI) when straight.
        knee_angle = -(math.pi - alpha_knee)

        # Calculate Hip Angle
        # Angle of the vector to target
        theta_target = math.atan2(target_x, abs(target_z)) 
        
        # Angle offset due to femur/tibia triangle
        # Cosine of angle at hip inside triangle
        cos_hip_offset = (self.l1**2 + r**2 - self.l2**2) / (2 * self.l1 * r)
        cos_hip_offset = max(-1.0, min(1.0, cos_hip_offset))
        alpha_hip = math.acos(cos_hip_offset)
        
        # Resulting Hip Angle
        # If x is forward (positive), hip rotates forward.
        hip_angle = theta_target + alpha_hip

        return hip_angle, knee_angle

    def generate_trot_path(self, t, cycle_time=0.5, stride_length=0.1, step_height=0.05):
        """
        Generates a foot trajectory for a trot gait.
        Returns target (x, z) relative to neutral stance.
        """
        phase = (t % cycle_time) / cycle_time
        
        if phase < 0.5:
            # Swing Phase (Moving leg forward + Lifting)
            # Simple Parabola
            progress = phase / 0.5
            x = (progress - 0.5) * stride_length
            z = math.sin(progress * math.pi) * step_height # Lift up
        else:
            # Stance Phase (Moving leg backward on ground)
            # Linear drag
            progress = (phase - 0.5) / 0.5
            x = (0.5 - progress) * stride_length
            z = 0 # On ground
            
        return x, z