// Assembly for Project: mission
$fn=50;

include </home/j/Desktop/viz_it/drone/output/mission_frame.scad>;

// Step: Mount Motors
translate([79.54875, 79.54875, 5]) include </home/j/Desktop/viz_it/drone/output/mission_motor.scad>;
translate([-79.54875, 79.54875, 5]) include </home/j/Desktop/viz_it/drone/output/mission_motor.scad>;
translate([-79.54875, -79.54875, 5]) include </home/j/Desktop/viz_it/drone/output/mission_motor.scad>;
translate([79.54875, -79.54875, 5]) include </home/j/Desktop/viz_it/drone/output/mission_motor.scad>;

// Step: Install FC Stack
translate([0, 0, 8]) include </home/j/Desktop/viz_it/drone/output/mission_fc.scad>;

// Step: Secure Camera
translate([0, 35, 10]) include </home/j/Desktop/viz_it/drone/output/mission_camera.scad>;

// Step: Attach Propellers
translate([79.54875, 79.54875, 15]) include </home/j/Desktop/viz_it/drone/output/mission_prop.scad>;
translate([-79.54875, 79.54875, 15]) rotate([0,0,180]) include </home/j/Desktop/viz_it/drone/output/mission_prop.scad>;
translate([-79.54875, -79.54875, 15]) include </home/j/Desktop/viz_it/drone/output/mission_prop.scad>;
translate([79.54875, -79.54875, 15]) rotate([0,0,180]) include </home/j/Desktop/viz_it/drone/output/mission_prop.scad>;

// Step: Mount Battery
translate([0, 0, -20]) include </home/j/Desktop/viz_it/drone/output/mission_battery.scad>;