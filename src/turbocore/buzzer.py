import time
import struct
from .pindaemon import write_pin_cmd, BOC
from .buzzer_pipe import PIPEPATH

from typing import Literal


def setup_pin_out(pin: int, initial: bool | None = None):
    cmd = b's' if initial is None else b'S'
    val = b'' if initial is None else struct.pack(BOC + '?', initial)
    write_pin_cmd(PIPEPATH, pin, cmd, val)


def set_pin(pin: int, state: bool):  # unreliable with consecutive calls
    val = struct.pack(BOC + '?', state)
    write_pin_cmd(PIPEPATH, pin, b'o', val)


def reset_pin(pin: int):
    write_pin_cmd(PIPEPATH, pin, b'r')


DEFAULT_BUZZER_PIN = 6  # GPIO 6, board pin 31 on RPi4b


def set_buzzer(state: bool | Literal[0, 1], pin=DEFAULT_BUZZER_PIN):
    state = bool(state)
    setup_pin_out(pin, initial=state)


def on(pin=DEFAULT_BUZZER_PIN):
    setup_pin_out(pin, initial=True)


def off(pin=DEFAULT_BUZZER_PIN):
    setup_pin_out(pin, initial=False)


def buzzfor(dton, dtoff=0.0):
    from turbocore import set_buzzer
    set_buzzer(1)
    time.sleep(dton)
    set_buzzer(0)
    time.sleep(dtoff)
