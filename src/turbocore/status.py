import time
import signal
import argparse
import subprocess
import pathlib as pl

import RPi.GPIO as GPIO
from turbocore import wsrgb
import turbocore.buttonman as buttonman
from rasadapter4 import front_sonar, set_buzzer

GPIO.setwarnings(False)

SPIN_PERIOD = 0.100

__stop = False


def waitif(t, spin_period=SPIN_PERIOD):
    n = t / spin_period
    for _ in range(int(n)):
        if __stop:
            return True
        time.sleep(spin_period)
    time.sleep(n % spin_period)
    if __stop:
        return True


def stop(exit_code=0):
    global __stop
    __stop = True
    set_buzzer(0)
    front_sonar.set_rgb_mode(0)
    front_sonar.fill_color(0)
    print("status.py will stop soon.")
    if buttonman:
        buttonman.TaskManager.unregister()
    print("Exiting status.py")
    import sys
    sys.exit(exit_code)  # exit the python script immediately


signal.signal(signal.SIGINT, lambda s, h: stop())


def check_interface(name):
    print(f"Waiting for {name} to connect...")
    path = pl.Path(f"/sys/class/net/{name}")
    if not (path / 'operstate').exists():
        return None
    connected = (path / 'operstate').read_text().strip() == 'up'
    if connected:
        print(f"Connected to {name}")
    return connected


def get_operstates():
    paths = pl.Path(f"/sys/class/net/").glob('*')
    return {path.name: (path / 'operstate').read_text().strip() for path in paths}


def check_connectivity(dest='8.8.8.8', timeout=1):
    print(f"Pinging {dest}")
    res = subprocess.run(
        f"ping -c 1 -W {timeout} {dest}", shell=True).returncode == 0
    if res:
        print(f"Connected to {dest}")
    return res


def quickbeep():
    set_buzzer(0)
    set_buzzer(1)
    waitif(0.3)
    set_buzzer(0)
    set_buzzer(0)


def start_breathing_blue():
    s = front_sonar
    s.set_rgb_mode(1)
    s.write_breath_register(s.REG_RGB1_R_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB1_G_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB1_B_BREATHING_CYCLE, 2000)
    s.write_breath_register(s.REG_RGB2_R_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB2_G_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB2_B_BREATHING_CYCLE, 2000)


def startup():
    print('startup')
    front_sonar.set_rgb_mode(0)
    front_sonar.fill_color(0)


def conn_waiting():
    buttonman.TaskManager.register_stoppable()
    start_breathing_blue()
    for _ in range(9999):
        if check_interface('wlan0') or check_interface('eth0') or check_connectivity():
            quickbeep()
            break


def wifi_waiting():
    buttonman.TaskManager().register_stoppable()
    start_breathing_blue()
    for _ in range(9999):
        if check_interface('wlan0'):
            quickbeep()
            break


actions = {
    'startup': startup,
    'conn_waiting': conn_waiting,
}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(choices=actions, dest='action')
    args = parser.parse_args()
    actions[args.action]()
    stop()
