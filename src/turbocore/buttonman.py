"""
TaskManager and ButtonManager class for managing button presses and releases.

When a button is clicked a certain number of times, the button manager will
choose the correct action.

"""


# from nt import stat
import os
import sys
import time
import itertools
import pathlib as pl
import threading
import subprocess
# import asyncio

import RPi.GPIO as GPIO

# typing
from typing import Any, Literal

from turbocore.debouncer import ButtonDebouncer
from turbocore.taskmanager import TaskManager
from turbocore.click import PushStateMachine

try:
    import statemachine
except (ImportError, ModuleNotFoundError):
    statemachine = None


# polyfill for 3.9 < 3.10
if 'pairwise' in dir(itertools):
    pairwise = itertools.pairwise
else:
    def pairwise(iterable):
        # pairwise('ABCDEFG') → AB BC CD DE EF FG
        iterator = iter(iterable)
        a = next(iterator, None)
        for b in iterator:
            yield a, b
            a = b


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


def stop_board():
    """Stop the motors, buzzer, leds, and running programs."""
    try:
        from turbocore import wsrgb, set_buzzer
        from rasadapter4 import motors, front_sonar
        try:
            import turbocore.buttonman as buttonman
            # note: stopping root processes requires root/sudo.
            # i.e. the 3-button-click battery checker requires sudo to stop
            # since that is spawned by this file, which was run by systemd as root.
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
        motors.speeds = [5, 5, 5, 5]
        motors.speeds = zeros
        time.sleep(0.1)
        motors.speeds = ones
        motors.speeds = ones
        time.sleep(0.1)
        motors.speeds = zeros
        motors.speeds = zeros
        set_buzzer(0)
        front_sonar.set_rgb_mode(0)
        front_sonar.fill_color(0)
        wsrgb.set_pixels(12, [0, 0])
    except Exception:
        pass


def reset_wifi():
    """Stop the AP and restart NetworkManager."""
    subprocess.Popen("nmcli con down HW-AP".split(' '))
    subprocess.Popen("systemctl restart NetworkManager.service".split(' '))


def start_ap():
    """Start the access point."""
    try_script("/turbopy/core/scripts/start_ap.sh")


def led_setup():  # not used
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LED1_PIN, GPIO.OUT)
    GPIO.output(LED1_PIN, 1)
    GPIO.setup(LED2_PIN, GPIO.OUT)
    GPIO.output(LED2_PIN, 0)


def try_script(path):
    """Run a script if it exists and is executable."""
    if not os.path.isfile(path):
        print(f"Tried to run script but it does not exist: {path}")
        return
    if not os.access(path, os.X_OK):
        perms = 0o766
        os.chmod(path, perms)
    subprocess.Popen(path)


class ActionMachine(statemachine.StateMachine):
    """Keeps track of button clicks and holds and performs the correct action."""
    # states
    idle = statemachine.State(initial=True)
    invalid = statemachine.State()
    c = statemachine.State()
    cc = statemachine.State()
    ccc = statemachine.State()
    cccc = statemachine.State()
    ccccc = statemachine.State()
    cccccc = statemachine.State()
    H = statemachine.State()
    cH = statemachine.State()
    ccH = statemachine.State()
    cccH = statemachine.State()

    # transitions (these get sent to the state machine)
    # ---
    # add single click
    b2_add_c = invalid.to.itself()
    b2_add_c |= idle.to(c)
    b2_add_c |= c.to(cc)
    b2_add_c |= cc.to(ccc)
    b2_add_c |= ccc.to(cccc)
    b2_add_c |= cccc.to(ccccc)
    b2_add_c |= ccccc.to(cccccc)
    b2_add_c |= invalid.from_(cccccc, H, cH, ccH, cccH)

    # add hold
    b2_add_H = invalid.to.itself()
    b2_add_H |= idle.to(H, after='do_1H')
    b2_add_H |= c.to(cH, after='do_2H')
    b2_add_H |= cc.to(ccH, after='do_3H')
    b2_add_H |= ccc.to(cccH, after='do_4H')
    b2_add_H |= invalid.from_(cccc, ccccc, cccccc, H, cH, ccH, cccH)

    # reset command (button unpressed for long enough)
    reset = invalid.to(idle)
    reset |= idle.to.itself()
    reset |= idle.from_(c, after='do_1c')
    reset |= idle.from_(cc, after='do_2c')
    reset |= idle.from_(ccc, after='do_3c')
    reset |= idle.from_(cccc, after='do_4c')
    reset |= idle.from_(ccccc, after='do_5c')
    reset |= idle.from_(cccccc, after='do_6c')
    reset |= idle.from_(H, cH, ccH, cccH)

    disable = lambda self: None  # noqa: E731
    enable = lambda self: None  # noqa: E731

    def do_1c(self):
        try_script("/home/pi/program1.sh")
        print("Started program1.sh")

    def do_2c(self):
        try_script("/home/pi/program2.sh")
        print("Started program2.sh")

    def do_3c(self):
        # subprocess.Popen("sudo python3 /home/pi/boot/battchk.py".split(' '))
        self.disable()
        time.sleep(0.05)
        os.system("/turbopy/.venv/bin/python -m turbocore.battchk --__listen_button_exit")
        self.enable()

    def do_4c(self):
        reset_wifi()
        led_setup()
        from turbocore.status import ap_off_beep
        ap_off_beep()
        subprocess.Popen("/turbopy/.venv/bin/python -m turbocore.status wifi_waiting".split(' '))

    def do_1H(self):
        TaskManager().close_all_registered()
        stop_board()

    def do_2H(self):
        TaskManager().close_all_registered()

    def do_3H(self):
        subprocess.Popen("/turbopy/.venv/bin/python -m turbocore.hardware_test".split(' '))

    def do_4H(self):
        start_ap()
        subprocess.Popen("/turbopy/.venv/bin/python -m turbocore.status hwap_waiting".split(' '))

    def do_5c(self):
        try_script("/home/pi/program5.sh")
        print("Started program5.sh")

    def do_6c(self):
        try_script("/home/pi/program6.sh")
        print("Started program6.sh")


class ButtonManager:
    """Manage setup and handling of KEY2 (closer to the USB ports)."""
    beeps = True

    def __init__(self) -> None:

        GPIO.setmode(GPIO.BCM)

        self.lock = threading.Lock()
        self.sequence = []
        self.serviced = True

        self.t_next = time.time_ns() + 100
        self.spin_period = 100E-3 * 1E9
        self.bouncetime = 45

        self.debouncers: dict[int, ButtonDebouncer] = {}

        self.key1_sm = PushStateMachine()
        self.key2_sm = PushStateMachine()
        self.actionsm = ActionMachine()

        asm = self.actionsm
        self.key2_sm.short_press = lambda: asm.send('b2_add_c')
        self.key2_sm.holding = lambda: asm.send('b2_add_H')
        self.key2_sm.done = lambda: asm.send('reset')

        asm.disable = self.clear_claims
        asm.enable = self.start_listening_both

    def btn_event(self, channel, state):
        """Handle a button event.

        This gets called by the button debouncer.

        See :py:meth:`ButtonManager.spin` for the main loop.
        """
        t = time.time_ns()
        while not self.lock.acquire_lock():  # SPINLOCK BRR
            time.sleep(0)  # wait until we can safely write to the sequence
        self.sequence.append((channel, state, t))
        self.serviced = False
        self.lock.release()
        # print(f"Key {1 if channel == KEY1_PIN else 2} {'down' if state == KDN else 'up'}")

    def start_listen_pin(self, keyi: Literal[1, 2], bouncetime=None,):
        """Acquire a pin and start listening on it.

        Parameters
        ----------
        keyi : Literal[1, 2]
            1 for KEY1_PIN, 2 for KEY2_PIN
        bouncetime : float, default=None
            Used to initialize the button debouncer. Default is :py:attr:`ButtonManager.bouncetime` (45ms).
        """
        print("Initializing edge listener on key", keyi)
        if bouncetime is None:
            bouncetime = self.bouncetime
        if keyi == 1:
            pin = KEY1_PIN
        elif keyi == 2:
            pin = KEY2_PIN
        else:
            msg = f"keyi must be 1 or 2, not {keyi}"
            raise ValueError(msg)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        debouncer = ButtonDebouncer(pin, self.btn_event, bouncetime=bouncetime)
        self.debouncers[keyi] = debouncer
        debouncer.start()
        GPIO.add_event_detect(pin, GPIO.BOTH, callback=debouncer)

    def start_listening_both(self, bouncetime=None):
        """Reserve and start listening to both button pins."""
        self.start_listen_pin(1, bouncetime=bouncetime)
        self.start_listen_pin(2, bouncetime=bouncetime)

    def clear_claim_pin(self, keyi: Literal[1, 2]):
        """Stop listening to and release a button pin."""
        print("Removing edge listener on key", keyi)
        if keyi == 1:
            pin = KEY1_PIN
        elif keyi == 2:
            pin = KEY2_PIN
        else:
            msg = f"keyi must be 1 or 2, not {keyi}"
            raise ValueError(msg)
        if keyi in self.debouncers and self.debouncers[keyi].is_alive():
            for i in range(3):
                try:
                    self.debouncers[keyi].join(timeout=self.bouncetime * (i + 1))
                except RuntimeError as err:
                    print(f"Failed to stop debouncer thread for key {keyi}: {err}")
            if self.debouncers[keyi].is_alive():
                print(f"Failed to stop debouncer thread for key {keyi}:"
                      " timed out while waiting to acquire thread lock")
            del self.debouncers[keyi]
        GPIO.remove_event_detect(pin)
        GPIO.cleanup(pin)

    def clear_claims(self):
        """Stop listening and release both pins."""
        print("Removing edge listeners")
        self.clear_claim_pin(1)
        self.clear_claim_pin(2)

    def bootup_check(self):
        print("Bootup period... if key 1 is held, AP mode will be set.")
        self.start_listening_both(45)

        if not self.sequence and GPIO.input(KEY1_PIN) == KDN:
            self.sequence = [(KEY1_PIN, KDN, time.time_ns())]
            print("key 1 already down")
        # if not self.sequence and GPIO.input(KEY2_PIN) == KDN:
        #     self.sequence = [(KEY2_PIN, KDN, time.time_ns())]

        time.sleep(6)

        # if the button is still held down, add a corresponding up entry
        if GPIO.input(KEY1_PIN) == KDN:
            self.sequence.append((KEY1_PIN, KUP, time.time_ns()))
        # if GPIO.input(KEY2_PIN) == KDN:
        #     self.sequence.append((KEY2_PIN, KUP, time.time_ns()))

        # stop listening
        self.clear_claims()

        # filter out each key in the sequence
        k1_seq = [x for x in self.sequence if x[0] == KEY1_PIN]
        # k2_seq = [x for x in self.sequence if x[0] == KEY2_PIN]

        def key_held_durations(sequence):
            lengths = []
            for a, b in pairwise(sequence):
                _, a_s, a_t = a
                _, b_s, b_t = b
                if not (a_s == KDN and b_s == KUP):
                    continue
                if b_t < a_t:
                    print("Congrats, you've created a time machine.")
                    continue
                dt = b_t - a_t
                lengths.append(dt)
            return lengths

        k1_held_durations = key_held_durations(k1_seq)  # durations in nanoseconds (ns)
        if any(t > 4E9 for t in k1_held_durations):  # if key 1 was held for longer than 4 seconds
            print("wifi reset triggered")
            # reset_wifi()
            start_ap()
            from turbocore.status import ap_beep
            ap_beep()

        self.sequence = []
        self.serviced = True
        # print(k1_held_durations)

    def wait_cycle(self):
        # i'm documenting this two years later. i have no idea
        # if/why this is necessary.
        dt = self.t_next - time.time_ns()  # nanoseconds
        if dt > self.spin_period:
            dt = self.spin_period
        if dt < 0:
            self.t_next = time.time_ns() + self.spin_period
        else:
            time.sleep(dt * 1E-9)

    def spin(self):
        """Send button presses to the correct button manager."""
        # If a button is pressed, the debouncer will need to wait for
        # the lock in order to record the event.
        # grab a copy of the sequence to process outside of the lock
        # spend as little time as possible inside the lock
        while not self.lock.acquire_lock():  # SPINLOCK BRR
            time.sleep(0)  # wait until we can safely write to the sequence
        sequence = self.sequence.copy()
        self.sequence = []
        self.serviced = True
        self.lock.release()

        # print(sequence)

        # send the button presses to the correct button manager
        for key, event, t in sequence:
            sm = self.key1_sm if key == KEY1_PIN else self.key2_sm
            sm.send('pushed' if event == KDN else 'released', t=t)
        now = time.time_ns()
        # if not any(key == KEY1_PIN for key, _, _ in sequence):
        #     self.key1_sm.cycle(t=now)
        # if not any(key == KEY2_PIN for key, _, _ in sequence):
        self.key2_sm.cycle(t=now)

        self.wait_cycle()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true')
    args = parser.parse_args()
    if args.clean:
        TaskManager().close_all_registered()
        sys.exit(0)
    manager = ButtonManager()
    manager.bootup_check()
    manager.start_listen_pin(2)
    try:
        subprocess.Popen("/home/pi/boot.sh")
    except FileNotFoundError:
        pass
    print('exited bootup check')
    while 1:
        manager.spin()
        # time.sleep(0)
