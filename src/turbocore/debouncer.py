import threading

import RPi.GPIO as GPIO


# adapted from https://raspberrypi.stackexchange.com/a/76738/63335
class ButtonDebouncer(threading.Thread):
    def __init__(self, pin, func=None, edge=GPIO.BOTH, bouncetime=200):
        super().__init__(daemon=True)

        def nop(*args):
            pass

        self.edge = edge
        self.func = nop if func is None else func
        self.pin = pin
        self.bouncetime = bouncetime / 1000

        self.lastpinval = GPIO.input(self.pin)
        self.lock = threading.Lock()

    def __call__(self, *args):
        if not self.lock.acquire(blocking=False):
            return

        t = threading.Timer(self.bouncetime, self.read, args=args)
        t.start()

    def read(self, *args):
        pinval = GPIO.input(self.pin)

        if (
            self.edge == GPIO.BOTH and pinval != self.lastpinval
            or self.edge == GPIO.FALLING and (pinval == 0 and self.lastpinval == 1)
            or self.edge == GPIO.RISING and (pinval == 1 and self.lastpinval == 0)
        ):
            self.func(args[0], pinval)

        self.lastpinval = pinval
        self.lock.release()
