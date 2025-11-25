
    use </home/j/Desktop/viz_it/drone/cad/library.scad>;
    $fn=30;
    pro_frame(wheelbase=193.718, arm_thick=4, plate_thick=2, stack_mounting=30.5);
    translate([offset, offset, 0]) pro_motor(2207, 0);
    translate([-offset, offset, 0]) pro_motor(2207, 0);
    translate([-offset, -offset, 0]) pro_motor(2207, 0);
    translate([offset, -offset, 0]) pro_motor(2207, 0);
    translate([0,0,4]) pro_stack(30.5, true);
    translate([0, -50.5, 20]) pro_camera(19.0, true);
    translate([0, 0, 35]) pro_battery(6, 1300);
    