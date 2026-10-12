import struct
from .pindaemon import ISROOT, BOC, unpack_packet_start, loop_read, mkpipe


if ISROOT:
    try:
        import rpi_ws281x as ws
    except ImportError:
        ws = None
        print("rpi_ws281x not found.")
else:
    ws = None


PIPENAME = "rgbd.pipe"
PIPEPATH = mkpipe(PIPENAME)


# DEFINE constants from swigged ws2811.h (in case rpi_ws281x hasn't loaded yet)

# 4 color R, G, B and W ordering
SK6812_STRIP_RGBW = 0x18100800
SK6812_STRIP_RBGW = 0x18100008
SK6812_STRIP_GRBW = 0x18081000
SK6812_STRIP_GBRW = 0x18080010
SK6812_STRIP_BRGW = 0x18001008
SK6812_STRIP_BGRW = 0x18000810
SK6812_SHIFT_WMASK = 0xf0000000

# 3 color R, G and B ordering
WS2811_STRIP_RGB = 0x00100800
WS2811_STRIP_RBG = 0x00100008
WS2811_STRIP_GRB = 0x00081000
WS2811_STRIP_GBR = 0x00080010
WS2811_STRIP_BRG = 0x00001008
WS2811_STRIP_BGR = 0x00000810

# predefined fixed LED types
WS2812_STRIP = WS2811_STRIP_GRB
SK6812_STRIP = WS2811_STRIP_GRB
SK6812W_STRIP = SK6812_STRIP_GRBW


strips = {}


def setup_default_pixels(
    n=2,
    pin=12,
    f=800000,
    dma_channel=10,
    brightness=120,
    channel=0,
    invert=False,
    strip_type=WS2811_STRIP_GRB,
):
    setup_pixels(
        num_leds=n,
        pin=pin,
        freq_hz=f,
        dma=dma_channel,
        invert=invert,
        brightness=brightness,
        channel=channel,
        strip_type=strip_type,
    )


def setup_pixels(
    num_leds: int,
    pin: int,
    freq_hz: int,
    dma: int,
    invert: bool,
    brightness: int,
    channel: int,
    strip_type: int,
):
    global strips
    try:
        strip = ws.PixelStrip(num_leds, pin, freq_hz, dma, invert, brightness, channel, strip_type)
        strips[pin] = strip
        strip.begin()
    except RuntimeError as err:
        strips.pop(pin, None)
        print(f"Error: {err}")
    # for i in range(strip.numPixels()):
    #     # strip.setPixelColor(i, ws.Color(0, 0, 0))
    #     strip.setPixelColor(i, 0)
    # strip.show()


def set_pixel(pin: int, i: int, color: int):
    if not ws:
        return
    strip = strips[pin]
    # color should be a rgb 24-bit or wrgb 32-bit integer (8-bit colors)
    if not isinstance(i, int):
        raise TypeError('Bad type received for pixel number.')
    if not isinstance(color, int):
        raise TypeError('Bad type received for rgb value.')
    if not 0 < i < 0xFF:
        raise ValueError('Pixel number out of range.')

    print(f"Setting pixel {i} to 0x{color:08x}")
    strip.setPixelColor(i, color)
    strip.show()


def set_strip_int(pin, array):
    if not ws:
        return
    strip = strips[pin]
    array = list(array)
    if not array:
        return
    if not isinstance(array, (tuple, list)):
        raise TypeError('Did not receive a useful iterable')

    # if all ints, convert to enumerated list
    if all(isinstance(x, int) for x in array):
        array = list(enumerate(array))

    # check types
    for x in array:
        if not isinstance(x, tuple) or not len(x) == 2:
            raise TypeError('Bad type received for RGB array.')
        i, color = x
        if not isinstance(i, int) or not isinstance(color, int):
            raise TypeError('Bad type received for RGB array.')

    for i, color in array:
        # color should be a rgb 24-bit or wrgb 32-bit integer (8-bit colors)
        # print(f"Setting pixel {i} to 0x{color:08x}")
        if not 0 <= i <= 0xFF:
            raise ValueError('Pixel number out of range.')
        strip.setPixelColor(i, color)
    strip.show()


WRGB_FORMAT = BOC + 'L'
WRGB_SIZE = struct.calcsize(WRGB_FORMAT)
AWRGB_FORMAT = BOC + 'BL'
AWRGB_SIZE = struct.calcsize(AWRGB_FORMAT)


DATA_FORMATS = {
    b'N': BOC + 'BLb?BBL',
}


def unpack_new(pin, data):
    fmt = DATA_FORMATS[b'N']
    args = list(struct.unpack(fmt, data))
    args.insert(1, pin)
    return args


def unpack_addressed(data):
    return struct.iter_unpack(AWRGB_FORMAT, data)


def unpack_unaddressed(data):
    return [x[0] for x in struct.iter_unpack(WRGB_FORMAT, data) if x and len(x) == 1]


def unpack_packets(commands):
    actions = unpack_packet_start([], commands)
    for action, pin, data in actions:
        a = str(action)[1:].strip('\'')
        print(f"{a:>3s} pin {pin: >3}: {data}")

        if action == b'N':
            args = unpack_new(pin, data)
            print(args)
            setup_pixels(*args)
        elif action == b'a':
            if pin not in strips:
                continue
            set_strip_int(pin, unpack_addressed(data))
        elif action == b'u':
            if pin not in strips:
                continue
            set_strip_int(pin, unpack_unaddressed(data))
        else:
            msg = f"Unknown action: {action}"
            raise ValueError(msg)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--setup_default_strip', action='store_true')
    parser.add_argument('--clear_strip', action='store_true')
    parser.add_argument('--listen', action='store_true')
    args = parser.parse_args()

    if args.setup_default_strip or args.clear_strip:
        setup_default_pixels()
    if args.clear_strip:
        set_strip_int(12, [0, 0])
    if not args.listen:
        raise SystemExit
    i = 0
    while True:
        loop_read(PIPEPATH, unpack_packets)
        i += 1
