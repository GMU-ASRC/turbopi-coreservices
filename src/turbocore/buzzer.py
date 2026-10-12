import struct
from .pindaemon import write_pin_cmd, BOC
from .buzzerd import PIPEPATH


def setup_pin_out(pin: int, initial: bool | None = None):
    cmd = b's' if initial is None else b'S'
    val = b'' if initial is None else struct.pack(BOC + '?', initial)
    write_pin_cmd(PIPEPATH, pin, cmd, val)


def set_pin(pin: int, state: bool):
    val = struct.pack(BOC + '?', state)
    write_pin_cmd(PIPEPATH, pin, b'o', val)


def reset_pin(pin: int):
    write_pin_cmd(PIPEPATH, pin, b'r')


buzzer = None
DEFAULT_BUZZER_PIN = 6  # GPIO 6, board pin 31 on RPi4b


def set_buzzer(state: bool):
    if buzzer is None:
        buzzer = 6
        setup_pin_out(buzzer, initial=state)
        return
    set_pin(buzzer, state)
