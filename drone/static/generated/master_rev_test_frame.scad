
    use </home/j/Desktop/viz_it/drone/cad/library.scad>;
    $fn=50;
    union() {
        frame_body(192.79999999999998, 2.5);
        translate([68.1548, 68.1548, 0]) motor_mount(12.0, 2, 3.2);
        translate([- 68.1548, 68.1548, 0]) motor_mount(12.0, 2, 3.2);
        translate([- 68.1548, - 68.1548, 0]) motor_mount(12.0, 2, 3.2);
        translate([68.1548, - 68.1548, 0]) motor_mount(12.0, 2, 3.2);
        translate([0,0,2.5]) fc_mount(25.5);
    }
    