#!/usr/bin/python3
from rasadapter4 import motors, front_sonar, set_buzzer
try:
    import turbocore.buttonman as buttonman
    buttonman.TaskManager().close_all_registered()
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
for _i in range(2):
    front_sonar.fill_color(0)
    # TODO: integrate rgbd
    # Board.RGB.setPixelColor(i, Board.PixelColor(r, g, b))
# Board.RGB.show()
