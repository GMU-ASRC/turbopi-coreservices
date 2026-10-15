"""
Provides LED indicator functions for startup sequence and buttonman.
"""


import time
import signal
import argparse
import subprocess
import pathlib as pl

import RPi.GPIO as GPIO
from turbocore import wsrgb, set_buzzer
import turbocore.buttonman as buttonman
from rasadapter4 import front_sonar

import typing


SPIN_PERIOD = 0.100

__stop = False


def waitif(t, spin_period=SPIN_PERIOD):
    # like time.sleep, but can be interrupted in increments of spin_period
    n = t / spin_period
    for _ in range(int(n)):
        if __stop:
            return True
        time.sleep(spin_period)
    time.sleep(n % spin_period)
    if __stop:
        return True


def stop(exit_code=0):
    # cleanup function
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


def cmdout(cmd: str) -> str:
    """Run a command and return the output."""
    return subprocess.run(cmd, shell=True, capture_output=True).stdout.decode('utf-8').strip()


# TODO: consider switching to python-sdbus-networkmanager?
# https://github.com/python-sdbus/python-sdbus-networkmanager
# https://python-sdbus-networkmanager.readthedocs.io/en/latest/


if typing.TYPE_CHECKING:
    from typing import overload
    @overload
    def get_nmcli(cmd: str, fields: str | tuple[str]) -> str | None: ...
    @overload
    def get_nmcli(cmd: str, fields: typing.Iterable[str]) -> typing.Dict[str, str] | None: ...


def get_nmcli(cmd, fields=()):
    """Run a command and return the output.

    This parses the output of nmcli show commands, which usually look like:

    .. code-block::
        GENERAL.DEVICE:                         eth0
        GENERAL.TYPE:                           ethernet
        GENERAL.HWADDR:                         DA:3A:DD:DD:EE:AA
        GENERAL.MTU:                            1500
        GENERAL.STATE:                          100 (connected)
        GENERAL.CONNECTION:                     netplan-eth0

    The command should be a valid nmcli command, but without the "nmcli".

    You can filter the output by specifying a list of fields.
    If you specify a single field (str or tuple with one str), the value will be returned as a string.
    Otherwise, a dictionary keyed by field names will be returned.
    """
    if isinstance(fields, str):
        fields = (fields,)
    sfields = ','.join(fields)
    if fields:
        cmd = f"--fields='{sfields}' {cmd}"
    try:
        out = cmdout(f"nmcli {cmd}")
    except Exception as e:
        print(e)
        return None
    if len(fields) == 1:
        return out.split(':')[-1].strip()
    return {
        k: v.strip()
        for line in out.splitlines()
        for k, v in [line.split(':', 1)]
    }


def get_interface_conname(name, ignore_con=()):
    """Get the connection name of an interface, if it is up.

    * If the interface cannot be found, returns ``None``.
    * If the interface is not up, returns ``False``.
    * If the interface is up but the connection name cannot be determined, returns ``' '`` (truthy).
    * If the connection name is in ignore_con, returns ``False``.
    * Otherwise, returns the connection name.
    """
    path = pl.Path(f"/sys/class/net/{name}")
    if not (path / 'operstate').exists():
        return None
    connected = (path / 'operstate').read_text().strip() == 'up'
    if connected:
        conname = get_nmcli(f"device show {name}", 'GENERAL.CONNECTION')
        if conname in ignore_con:
            return False
        if not conname:
            return ' '
        return conname
    return False


def check_interface(name, ignore_con=()):
    """Check if an interface is connected.

    Parameters
    ----------
    name : str
        Interface name.
    ignore_con : tuple, default=()
        Connection names to ignore.

    Returns
    -------
    bool
        True if connected, False otherwise.
    """
    conname = get_interface_conname(name, ignore_con)
    if not conname:
        return False
    print(f"Connected to {name} ({conname})")
    return bool(conname)


def get_operstates():
    """Get the operstate of all network interfaces.

    Returns
    -------
    dict
        Dictionary of interface names to operstates.
    """
    paths = pl.Path(f"/sys/class/net/").glob('*')
    return {path.name: (path / 'operstate').read_text().strip() for path in paths}


def check_connectivity(dest='8.8.8.8', timeout=1):
    """Check if a host is reachable.

    Parameters
    ----------
    dest : str, default='8.8.8.8'
        Destination host.
    timeout : int, default=1
        Timeout in seconds.

    Returns
    -------
    bool
        True if reachable, False otherwise.
    """
    print(f"Pinging {dest}")
    res = subprocess.run(
        f"ping -c 1 -W {timeout} {dest}", shell=True).returncode == 0
    if res:
        print(f"Connected to {dest}")
    return res


def quickbeep():
    """Beep for 0.3 seconds."""
    set_buzzer(0)
    set_buzzer(1)
    waitif(0.3)
    set_buzzer(0)
    set_buzzer(0)


def ap_beep():
    """Beep pattern for starting HW-AP."""
    from turbocore.buzzer import buzzfor
    buzzfor(.1, .1)
    buzzfor(.1, .1)
    buzzfor(.1, .12)
    buzzfor(.3, .2)


def ap_off_beep():
    """Beep pattern for re-enabling WiFi."""
    from turbocore.buzzer import buzzfor
    buzzfor(.3, .08)
    buzzfor(.08, .06)
    buzzfor(.1, .13)
    buzzfor(.08, .2)


def start_breathing_blue(t=2000):
    """Blue breathing cycle for waiting for WiFi/network connection."""
    s = front_sonar
    s.set_rgb_mode(1)
    s.write_breath_register(s.REG_RGB1_R_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB1_G_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB1_B_BREATHING_CYCLE, t)
    s.write_breath_register(s.REG_RGB2_R_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB2_G_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB2_B_BREATHING_CYCLE, t)


def start_breathing_green(t=3000):
    """Green breathing cycle to signal HW-AP mode."""
    s = front_sonar
    s.set_rgb_mode(1)
    s.write_breath_register(s.REG_RGB1_R_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB1_G_BREATHING_CYCLE, t)
    s.write_breath_register(s.REG_RGB1_B_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB2_R_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB2_G_BREATHING_CYCLE, t)
    s.write_breath_register(s.REG_RGB2_B_BREATHING_CYCLE, 0)


def startup():
    print('startup')
    front_sonar.set_rgb_mode(0)
    front_sonar.fill_color(0)


def conn_waiting():
    """Startup script for waiting for network connection.
    Ignores HW-AP connections.
    If HW-AP is detected, breath green and stop waiting.
    """
    buttonman.TaskManager.register_stoppable()
    start_breathing_blue()
    print("Waiting for network connection...")
    for i in range(9999):
        if (
            check_interface('wlan0', ignore_con=('HW-AP',))
            or check_interface('eth0')
            or check_connectivity()
        ):
            quickbeep()
            break
        elif i > 5 and get_interface_conname('wlan0') == 'HW-AP':
            ap_beep()
            breath_green_wait()
        waitif(0.5)


def wifi_waiting(min_time=2):
    """Script for waiting for WiFi connection.

    Intended to be used with the `buttonman` module,
    so ``min_time`` is a wait time before checking for wifi connection,
    so the user has a chance to see the blue indicator before we turn it off.
    """
    buttonman.TaskManager().register_stoppable()
    start_breathing_blue()
    print(f"Waiting for wifi connection...")
    waitif(min_time)
    for _ in range(9999):
        if check_interface('wlan0'):
            quickbeep()
            break
        waitif(0.5)


def hwap_waiting():
    """Script for waiting for HW-AP connection.

    Intended to be used with the `buttonman` module.
    """
    buttonman.TaskManager().register_stoppable()
    start_breathing_green()
    print("Waiting for HW-AP connection...")
    i = 0  # avoid unbound var warning
    for i in range(1200):
        if get_interface_conname('wlan0') == 'HW-AP':
            ap_beep()
            break
        waitif(0.5)
        i = i  # explicit assignment to avoid code checker warning
    if i < 4:
        # If it finished too early, breath green one more cycle
        # so that the user has a chance to see.
        breath_green_wait()


def breath_green_wait(ms=3000):
    """Breath a single green cycle. Blocking."""
    buttonman.TaskManager().register_stoppable()
    front_sonar.set_rgb_mode(0)
    front_sonar.fill_color(0x00FF00)
    waitif(0.01)
    start_breathing_green(ms)
    waitif(ms * 3 / 2000)
    front_sonar.set_rgb_mode(0)
    front_sonar.fill_color(0)


#: Dispatch table for actions that this script can be called with.
actions = {
    'startup': startup,
    'conn_waiting': conn_waiting,
    'wifi_waiting': wifi_waiting,
    'hwap_waiting': hwap_waiting,
    'breath_green_wait': breath_green_wait,
}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(choices=actions, dest='action')
    args = parser.parse_args()
    actions[args.action]()

    GPIO.setwarnings(False)
    signal.signal(signal.SIGINT, lambda s, h: stop())
    stop()
