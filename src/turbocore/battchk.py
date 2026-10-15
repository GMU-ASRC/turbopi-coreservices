#!/usr/bin/python3
# coding=utf8
"""
Battery checker program and watchdog.

If KEY2 is pressed three times, this program will run in ``check`` mode.

In ``check`` mode, this program sends a sequence of beeps
to audibly inform the user of the average cell voltage of the battery pack.

For example, if the average cell voltage is 4.0 V, it will beep like this:

.. code-block:: none

    *beep* *beep* *beep* *beep*    *pause*    *short beep*

The short beep indicates a 0 decimal place.

The LEDs will also light up with the pattern and the color will indicate
good/badness.

This will continue up to 10 times or until the program is stopped by pressing
either button.

In ``watch`` mode, this program should be started as a service. It will
check the voltage every half a second. If the voltage is consistently
too low (below 3.5 V) for over 10 seconds, it will stop all running
programs and begin the ``check`` routine to warn the user. This may be
cancelled for up to 2 minutes. The LEDs will also flash red afterwards.
"""

import sys
import signal

import os
import time
import struct
import argparse

import RPi.GPIO as GPIO

from rasadapter4 import front_sonar, battery
from turbocore import wsrgb, set_buzzer

try:
    from rich import print
    import rich
except (ImportError, ModuleNotFoundError):
    rich = None

import warnings
try:
    import turbocore.buttonman as buttonman
except (ImportError, ModuleNotFoundError):
    buttonman = None
    warnings.warn("buttonman was not imported, so no processes can be registered. This means the process can't be stopped by buttonman.",  # noqa: E501
                  ImportWarning, stacklevel=2)

import typing

sys.stdout.reconfigure(encoding="utf-8")


#######

key1_debouncer = None
key2_debouncer = None

environ_silent = os.environ.get('silent', None)
do_beeps = environ_silent is None or environ_silent.lower() == 'false'
do_flash = True

# BCM NUMBERING
#: BCM numbering for GPIO pin 13, board pin 33.
KEY1_PIN = 13
#: BCM numbering for GPIO pin 23, board pin 16.
KEY2_PIN = 23
#: BCM numbering for GPIO pin 6, board pin 31. See :py:mod:`turbocore.buzzer`.
BUZZER_PIN = 6
KDN = GPIO.LOW
KUP = GPIO.HIGH
#: BCM numbering for GPIO pin 16, board pin 36. Blue status LED1 on rasadapter.
LED1_PIN = 16
#: BCM numbering for GPIO pin 26, board pin 37. Green status LED2 on rasadapter.
LED2_PIN = 26

GPIO.setwarnings(False)

#: Threshold for bad cell voltage.
BAD_CELL_VOLTAGE = 3.45

#: Number of times to run the beep/flash sequence before stopping.
n = 10

__stop = False
button_listen = False
button_states = [KUP, KUP]

rgb = {
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'lime': (80, 222, 0),
    'yellow': (200, 200, 0),
    'orange': (255, 50, 0),
    'black': (0, 0, 0),
    'white': (255, 255, 255),
}

SPIN_PERIOD = 0.100

rgb_initialized = False


def clamp(x, xmin, xmax):
    return min(xmax, max(xmin, x))


def initialize_rgb():
    global rgb_initialized
    if rgb_initialized:
        return
    try:
        wsrgb.setup_default_pixels()
        rgb_initialized = True
    except OSError:
        pass


def waitif(t, spin_period=SPIN_PERIOD):
    """Wait in chunks of ``spin_period`` seconds.

    This way, if the program is stopped, it will wait at most ``SPIN_PERIOD`` seconds.

    Parameters
    ----------
    t : float
        Time to wait in seconds.
    spin_period : float, default=SPIN_PERIOD
        Time to wait in between chunks.

    Returns
    -------
    bool
        True if the program was stopped, False otherwise.
    """
    n = t / spin_period
    for _ in range(int(n)):
        if __stop:
            return True
        time.sleep(spin_period)
    time.sleep(n % spin_period)
    if __stop:
        return True


def buzzer(value):
    if do_beeps:
        set_buzzer(bool(value))


def all_leds(r, g, b):
    """Set all the LEDs to the given color."""
    if not do_flash:
        return
    r, g, b = int(r), int(g), int(b)
    color = int.from_bytes(struct.pack('>BBB', r, g, b), 'big')
    front_sonar.set_rgb_mode(0)
    front_sonar.fill_color(color)  # front sonar lights
    initialize_rgb()
    wsrgb.set_pixels(12, [color, color])  # board neopixels


def breath_sonar_red():
    """Set the front sonar lights to flash red. Non-blocking."""
    s = front_sonar
    s.set_rgb_mode(1)
    s.write_breath_register(s.REG_RGB1_R_BREATHING_CYCLE, 400)
    s.write_breath_register(s.REG_RGB1_G_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB1_B_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB2_R_BREATHING_CYCLE, 400)
    s.write_breath_register(s.REG_RGB2_G_BREATHING_CYCLE, 0)
    s.write_breath_register(s.REG_RGB2_B_BREATHING_CYCLE, 0)


def ledbeepfor(rgbv, dton, dtoff=0.0):
    """Turn on the LEDs and buzzer for a period of time, then stop and wait for another period."""
    if __stop:
        return
    buzzer(1)
    all_leds(*rgbv)
    if waitif(dton):
        return
    buzzer(0)
    all_leds(*rgb['black'])
    if waitif(dtoff):
        return


def mean(li):
    return sum(li) / len(li)


def median(li):
    return sorted(li)[int(len(li) / 2)]


def voltage_detection():
    """Get the total cell voltage."""
    try:
        waitif(0.1)
        v = battery.voltage
        if 0 < v < 16:
            return v
    except Exception as e:
        print('Error', e)


def voltage_color(voltage: float):
    """Specifies a color based on the cell voltage.

    Parameters
    ----------
    voltage : float
        Single-cell voltage in volts (~3.7V)

    Returns
    -------
    tuple[int, int, int]
        RGB color.
    """
    if voltage < 3.5:
        return rgb['red']
    if 3.5 <= voltage < 3.7:
        return rgb['orange']
    if 3.7 <= voltage < 3.9:
        return rgb['yellow']
    if 3.9 <= voltage < 4.05:
        return rgb['lime']
    if voltage >= 3.9:
        return rgb['green']
    return (100, 0, 100)


def voltage_goodness(voltage: float | None):
    """Return a string indicating the battery status."""
    if voltage is None:
        return "[░░░░░] ERROR"
    if 0.8 <= voltage < 3.4:
        return "[    ]  VERY LOW CHARGE IMMEDIATELY"
    if 3.4 <= voltage < 3.5:
        return "[■   ] Low "
    if 3.5 <= voltage < 3.7:
        return "[■■  ] Normal"
    if 3.7 <= voltage < 3.9:
        return "[■■■ ] Normal"
    if 3.9 <= voltage < 4.05:
        return "[■■■ ] Near Full"
    if 4.05 <= voltage < 5:
        return "[■■■■] Full"
    return "[░░░░░] ERROR"


def rich_goodness(voltage: float | None):
    """Extra pretty bar/info below the battery status"""
    from rich.style import Style
    from rich.color_triplet import ColorTriplet
    from rich.color import blend_rgb, Color
    from rich.progress_bar import ProgressBar
    console = rich.get_console()
    red = ColorTriplet(200, 0, 0)
    yellow = ColorTriplet(255, 255, 0)
    green = ColorTriplet(40, 255, 0)
    if voltage is None:
        style = Style(color=Color.parse('#111111'), bgcolor=Color.parse('#BBBBBB'),
                      blink=True, blink2=True)
        console.print("      -- Measurement Error --      ", style=style)
        console.print()
        return
    elif voltage < 3.2:
        style = Style(color=Color.parse('#666666'), bgcolor=Color.parse('#FF2000'),
                      blink=True, blink2=True, bold=True)
        console.print("    CRITICALLY LOW   STOP AND CHARGE NOW    ", style=style)
        console.print()
        return
    amount = voltage * 20 - 64
    amount = clamp(amount, 0, 20)
    if amount > 10:
        color = blend_rgb(yellow, green, cross_fade=(amount - 10) / 10)
    else:
        color = blend_rgb(red, yellow, cross_fade=amount / 10)
    color = [clamp(x, 0, 255) for x in color]
    style = Style(color=Color.from_rgb(*color))
    bar = ProgressBar(
        width=20,
        total=20,
        completed=round(amount),
        style=Style(color=Color.parse('#777777')),
        complete_style=style,
        finished_style=style,
    )
    console.show_cursor(False)
    console.print(bar)
    console.print()


if typing.TYPE_CHECKING:
    from typing import overload
    @overload
    def decimal_split(x: float, precision: int = 1, mode: str = 'digit') -> tuple[tuple[int, ...], tuple[int, ...]]: ...
    @overload
    def decimal_split(x: float, precision: int = 1, mode: str = 'whole') -> tuple[int, int]: ...


def decimal_split(x: float, precision=1, mode='digit'):
    """Lexically split a float into the whole portion and a decimal portion.

    Parameters
    ----------
    x : float
    precision : int, default=1
        Number of decimal places for string formatting.
    mode : str, default='digit'
        ``'digit'`` to return separate integers for each decimal place,
        or 'whole' to return just the whole/decimal portions.

    Returns
    -------
    _type_
        _description_
    """
    x = round(x, precision)
    s = f"{x:.{precision}f}"
    a, b = s.split('.')
    if mode == 'digit':
        return tuple(tuple(int(x) for x in part) for part in (a, b))
    if mode == 'whole':
        return int(a), int(b)


def beepn(n, color):
    """Beep a certain number of times, or do a short beep for ``0``

    Parameters
    ----------
    n : int
        Number of beeps to do.
    color : tuple[int, int, int]
        RGB color.
    """
    if n == 0:
        ledbeepfor(color, .09, .2)
        return
    for _ in range(n):
        ledbeepfor(color, .3, .2)


def measure_voltage(n: int = 1):
    """Measure the pack voltage ``n`` times and estimate the single-cell voltage.

    Parameters
    ----------
    n : int, default=1
        Number of times to attempt to measure the voltage.

    Returns
    -------
    tuple[float, list[float]]
        Median single-cell voltage, and a list of successful measurements of the pack voltage.
    """
    measurements = [voltage_detection() for _ in range(n)]
    measurements = [x for x in measurements if x is not None]
    if not measurements:
        return None, None
    voltage = median(measurements)
    cell_voltage = voltage / 2
    return cell_voltage, measurements


def loop():
    """Main beeping/flashing routine."""
    v, _ = measure_voltage(5)
    color = voltage_color(v)
    a, b = decimal_split(v, precision=1, mode='whole')
    print(f"{a}.{b}\t{v:.3f}\t{color}")
    beepn(a, color)
    if waitif(1):
        return
    beepn(b, color)
    if waitif(2.2):
        return


def stop():
    global __stop
    __stop = True
    buzzer(0)
    all_leds(*rgb['black'])
    print("battchk.py will stop soon.")
    if button_listen:
        print("Waiting for all buttons to be released...")
        return
        # while True:  # let the listener handle the exit.
        #     if not any(btn_check()):
        #         break
        #     time.sleep(0.1)
    if buttonman:
        buttonman.TaskManager.unregister()
    print("Exiting battchk.py")
    sys.exit()  # exit the python script immediately


def main():
    """Start the main beep/flash routine, or print voltage in stealth mode."""
    if do_beeps:
        set_buzzer(0)  # initialize buzzer
    if do_flash:
        front_sonar.set_rgb_mode(0)
    for _ in range(n):
        if not __stop:
            loop()
    if not n:  # if n == 0 or None
        print("Measuring...")
        cell, measurements = measure_voltage(10)
        print(measurements)
        print(f"Avg. Cell Voltage:\t{cell:.3f}")
        print(f"Status: \t\t{voltage_goodness(cell)}")
        if rich:
            rich_goodness(cell)
        return
    while __stop and button_listen and KDN in button_states:
        time.sleep(SPIN_PERIOD)  # trap if waiting for buttons to be unpressed...


def _watch():
    """Check if the battery is consistently too low."""
    global __stop
    cell, _ = measure_voltage(2)
    # if the cell voltage is too low, check if it remains too low for a while
    if cell and cell < BAD_CELL_VOLTAGE:
        # take 20 measurements over roughly 10 seconds
        measurements = []
        for _ in range(20):
            total = voltage_detection()
            if total is not None:
                measurements.append(total / 2)
            waitif(0.49)
        if not measurements:
            print("err")
            return
        # if the best measurement is still too low, stop all processes
        best = max(measurements)
        print(best)
        if best < BAD_CELL_VOLTAGE:
            print(f"Battery voltage is low: {best}."
                  " Stopping all registered processes.")
            buttonman.TaskManager().close_all_registered()
            buttonman.stop_board()
            # TODO: try to acquire button so user can cancel the beeping. Would need to release afterwards.
            main()  # run the main beep/flash routine to warn anybody nearby
            __stop = False  # reset the stop flag so waitif() works properly
            breath_sonar_red()  # leave the sonar lights flashing red
            waitif(120, spin_period=1)  # give the user 2 minutes to cancel


def watch():
    """Battery watchdog routine."""
    global __stop
    # for constantly checking the voltage every 10 seconds
    while True:
        __stop = False
        try:
            _watch()
        except Exception as err:
            print(err)
        waitif(10, spin_period=0.5)


def btn_check():
    global button_states
    button_states = [GPIO.input(KEY1_PIN), GPIO.input(KEY2_PIN)]
    return KDN in button_states


def btn_handler(channel, state):
    global button_states
    button_i = 0 if channel == KEY1_PIN else 1
    button_states[button_i] = state
    print(button_states)
    if KDN in button_states:
        stop()
        print("made it out of handler")
    elif __stop:  # both buttons are unpressed
        print("Both buttons unpressed now.")
        print("Exiting battchk.py via handler")
        if buttonman:
            buttonman.TaskManager.unregister()
        sys.exit()  # exit the python script immediately


def setup_buttons():
    global key1_debouncer, key2_debouncer
    print("Adding listeners to stop battchk.py")
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(KEY1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(KEY2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    key1_debouncer = buttonman.ButtonDebouncer(KEY1_PIN, btn_handler, bouncetime=30)
    key2_debouncer = buttonman.ButtonDebouncer(KEY2_PIN, btn_handler, bouncetime=30)
    key1_debouncer.start()
    key2_debouncer.start()
    GPIO.add_event_detect(KEY1_PIN, GPIO.BOTH, callback=key1_debouncer)
    GPIO.add_event_detect(KEY2_PIN, GPIO.BOTH, callback=key2_debouncer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--__listen_button_exit', action='store_true')
    parser.add_argument('--silent', action='store_true', help="Flash lights but don't beep.")
    parser.add_argument('-q', '--quiet', action='store_true', help="Flash lights but don't beep.")
    parser.add_argument('-s', '--stealth', action='store_true', help="Only report battery status to console.")
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('-n', type=int, default=None)
    args = parser.parse_args()

    if not args.watch:
        try:
            buttonman.TaskManager.register_stoppable()
        except Exception as e:
            warnings.warn("buttonman.TaskManager.register_stoppable() failed. This means the process can't be stopped by buttonman.\n"  # noqa: E501
                          + str(e), RuntimeWarning, stacklevel=2)

    if args.silent or args.quiet:
        do_beeps = False

    if args.n is not None:
        n = args.n

    if args.stealth:
        if args.n is None:
            n = 0
        do_beeps = False
        do_flash = False

    signal.signal(signal.SIGINT, lambda s, h: stop())

    if args.watch:
        watch()
    else:
        button_listen = args.__listen_button_exit
        if button_listen and buttonman:
            setup_buttons()
        elif button_listen:
            raise ImportError("Requested to run in button stop mode, but buttonman module couldn't be imported! Exiting...")
        main()
        if buttonman:
            buttonman.TaskManager.unregister()
