
    use </home/j/Desktop/viz_it/drone/cad/library.scad>;
    $fn=50;
    
    // 1. The Frame
    pro_frame(wheelbase=300.0, arm_thick=4, plate_thick=2, stack_mounting=30.5);

    // 2. Motors (Rotated and placed)
    translate([offset, offset, 0]) pro_motor(2207, 0);
    translate([-offset, offset, 0]) pro_motor(2207, 0);
    translate([-offset, -offset, 0]) pro_motor(2207, 0);
    translate([offset, -offset, 0]) pro_motor(2207, 0);

    // 3. Props (Lifted up, visualized)
    // Standard pitch 4.3, 3 blades
    translate([offset, offset, 15]) pro_prop(5.0, 4.3, 3);
    translate([-offset, offset, 15]) rotate([0,0,90]) pro_prop(5.0, 4.3, 3); 
    translate([-offset, -offset, 15]) pro_prop(5.0, 4.3, 3);
    translate([offset, -offset, 15]) rotate([0,0,90]) pro_prop(5.0, 4.3, 3);

    // 4. Electronics Stack
    translate([0,0,4]) pro_stack(30.5, true);

    // 5. Camera (Front mounted)
    // Heuristic: Place camera at the front edge of the 'cage' area
    translate([0, -50.5, 20]) pro_camera(19.0, true);

    // 6. Battery (Top mounted)
    translate([0, 0, 35]) pro_battery(6, 1300);
    