"""
Control the board's buzzer (or GPIO pin) via the buzzerd daemon.
"""


import time
import struct
from .pindaemon import write_pin_cmd, BOC
from .buzzer_pipe import PIPEPATH

from typing import Literal


def setup_pin_out(pin: int, initial: bool | None = None):
    """Tell the daemon to setup the pin and/or set the pin state.

    Parameters
    ----------
    pin : int
        GPIO pin number using BCM numbering.
    initial : bool, default=None
        Initial pin state.
    """
    cmd = b's' if initial is None else b'S'
    val = b'' if initial is None else struct.pack(BOC + '?', initial)
    write_pin_cmd(PIPEPATH, pin, cmd, val)


def set_pin(pin: int, state: bool):  # unreliable with consecutive calls
    """Tell the daemon to set the pin state.

    The pin must be setup first with `setup_pin_out`.

    Parameters
    ----------
    pin : int
        GPIO pin number using BCM numbering.
    state : bool
        Pin state. ``True`` for high, ``False`` for low.
    """
    val = struct.pack(BOC + '?', state)
    write_pin_cmd(PIPEPATH, pin, b'o', val)


def reset_pin(pin: int):
    """Tell the daemon to reset and release the pin."""
    write_pin_cmd(PIPEPATH, pin, b'r')


#: Default buzzer pin. GPIO 6, board pin 31 on RPi4b.
DEFAULT_BUZZER_PIN = 6  # GPIO 6, board pin 31 on RPi4b


def set_buzzer(state, pin=DEFAULT_BUZZER_PIN):
    """Set the buzzer state.

    Parameters
    ----------
    state : bool | Literal[0, 1]
        ``True`` for high, ``False`` for low.
    pin : int, default=DEFAULT_BUZZER_PIN
        GPIO pin number using BCM numbering.
    """
    state = bool(state)
    setup_pin_out(pin, initial=state)


def on(pin=DEFAULT_BUZZER_PIN):
    """Set the buzzer state to high/on."""
    setup_pin_out(pin, initial=True)


def off(pin=DEFAULT_BUZZER_PIN):
    """Set the buzzer state to low/off."""
    setup_pin_out(pin, initial=False)


def buzzfor(dton, dtoff=0.0):
    """Set the buzzer state for a period of time (blocking).

    Parameters
    ----------
    dton : float
        Time to set the buzzer state to high/on.
    dtoff : float, default=0.0
        Time to wait after setting the buzzer state to low/off before returning.
    """
    from turbocore import set_buzzer
    set_buzzer(1)
    time.sleep(dton)
    set_buzzer(0)
    time.sleep(dtoff)
