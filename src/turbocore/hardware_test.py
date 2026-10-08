#!/usr/bin/python3
# coding=utf8
import sys
import time
import signal
from rasadapter4 import motors, servos, front_sonar, set_buzzer
try:
    import turbocore.buttonman as buttonman
    buttonman.TaskManager().close_all_registered()
except Exception:
    pass


def stop(sig, handler):
    motors.stop()
    if buttonman:
        buttonman.TaskManager.unregister()
    sys.exit()  # exit the python script immediately


signal.signal(signal.SIGINT, stop)


servos[0].set_pulse(1800, use_time=300)
time.sleep(0.3)
servos[0].set_pulse(1500, use_time=300)
time.sleep(0.3)
servos[0].set_pulse(1200, use_time=300)
time.sleep(0.3)
servos[0].set_pulse(1500, use_time=300)
time.sleep(1.5)

servos[1].set_pulse(1200, use_time=300)
time.sleep(0.3)
servos[1].set_pulse(1500, use_time=300)
time.sleep(0.3)
servos[1].set_pulse(1800, use_time=300)
time.sleep(0.3)
servos[1].set_pulse(1500, use_time=300)
time.sleep(1.5)

for i in range(4):
    motors[i] = 45
    time.sleep(0.5)
    motors.stop()
    time.sleep(1)
