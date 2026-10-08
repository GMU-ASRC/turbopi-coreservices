#!/usr/bin/python3
from turbocore import wsrgb
from rasadapter4 import motors, front_sonar, set_buzzer
try:
    import turbocore.buttonman as buttonman
    buttonman.TaskManager().close_all_registered()
except Exception:
    pass
try:
    wsrgb.setup_default_pixels()
except Exception:
    pass
zeros = [0, 0, 0, 0]
ones = [1, 1, 1, 1]
# spam
motors.speeds = zeros
motors.speeds = ones
motors.speeds = zeros
motors.speeds = ones
motors.speeds = ones
motors.speeds = zeros
motors.speeds = zeros
set_buzzer(0)
front_sonar.set_rgb_mode(0)
front_sonar.fill_color(0)
wsrgb.set_pixels(12, [0, 0])
