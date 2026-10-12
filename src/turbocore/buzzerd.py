import struct
import RPi.GPIO as GPIO

from .pindaemon import mkpipe, unpack_packet_start, loop_read, BOC

PIPENAME = "buzzer.pipe"
PIPEPATH = mkpipe(PIPENAME)

GPIO.setmode(GPIO.BCM)

GPIO.setmode(GPIO.BCM)

pins = {}
pwms: dict[int, GPIO.PWM] = {}


def unpack_packets(commands):
    actions = unpack_packet_start([], commands)
    for action, pin, data in actions:
        a = str(action)[1:].strip('\'')  # remove the `b''` from cmd string representation
        print(f"{a:>3s} pin {pin: >3}: {data}")
        if action == b'S':
            state = struct.unpack(BOC + '?', data)[0]
            GPIO.setup(pin, GPIO.OUT, initial=state)
            pins[pin] = GPIO.OUT
        elif action == b's':
            GPIO.setup(pin, GPIO.OUT)
            pins[pin] = GPIO.OUT
        elif action == b'o':
            state = struct.unpack(BOC + '?', data)[0]
            GPIO.output(pin, state)
        elif action == b'r':
            GPIO.cleanup(pin)
        elif action == b'P':
            freq = struct.unpack(BOC + 'f', data)[0]
            pwms[pin] = GPIO.PWM(pin, freq)
        elif action == b'f':
            freq = struct.unpack(BOC + 'f', data)[0]
            if pin not in pwms:
                pwms[pin] = GPIO.PWM(pin, freq)
            else:
                pwms[pin].ChangeFrequency(freq)
        elif action == b'd':
            duty = struct.unpack(BOC + 'f', data)[0]
            pwms[pin].start(duty)
        elif action == b'D':
            pwms[pin].stop()
        else:
            msg = f"Unknown action: {action}"
            raise ValueError(msg)


if __name__ == '__main__':
    i = 0
    while True:
        loop_read(PIPEPATH, unpack_packets)
        i += 1
