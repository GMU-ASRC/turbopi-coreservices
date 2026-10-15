"""
Daemon for controlling WS281x LEDs connected to the GPIO pins.

rpi_ws281x needs root privileges due to the strict timing requirements
of neopixels. This daemon runs as root and uses the
`rpi_ws281x <https://github.com/rpi-ws281x/rpi-ws281x-python>`_ library
to control the LEDs.

This module contains the functions to read commands from other processes,
and the functions to actually execute the commands and control the LEDs.

Supports RGB and RGBW LEDs (RGBW is not yet tested).
"""


import struct
from .pindaemon import ISROOT, BOC, unpack_packet_start, loop_read, mkpipe


if ISROOT:
    try:
        import rpi_ws281x as ws
    except ImportError:
        ws = None
        print("rpi_ws281x not found.")
else:
    ws = None  # don't load rpi_ws281x if not root
    # avoids ugly print that appears when the C extension is loaded


#: Name of the pipe for the daemon.
PIPENAME = "rgbd.pipe"
#: Path to the pipe for the daemon (``/tmp/rgbd.pipe``).
PIPEPATH = mkpipe(PIPENAME)  # if this is daemon process, create pipe if it doesn't exist


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

#: Dictionary of initialized strips, keyed by pin number.
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
    """Initialize a strip object with the given settings.

    The strop object is stored in the global ``strips`` dictionary.

    Parameters
    ----------
    num_leds : int
        Number of LEDs on the strip.
    pin : int
        GPIO Pin number.
    freq_hz : int
        Signal rate.
    dma : int
        DMA channel. WARNING: This is not checked.
        A wrong value may brick your Pi or SD card.
    invert : bool
        Whether to invert the signal.
    brightness : int
        Scaling factor for the brightness. 0 to 255.
    channel : int
        PWM channel.
    strip_type : int
        Strip type. See ``rpi_ws281x.ws2811`` for details.
    """
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
    """Set a single pixel to a color.

    The color is shown immediately, i.e. the entire strip is updated.

    Parameters
    ----------
    pin : int
        GPIO Pin number.
    i : int
        Pixel number.
    color : int
        RGB/RGBW color. 24-bit or 32-bit integer.
    """
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
    """ Set all pixels according to a list of colors.

    Parameters
    ----------
    pin : int
        Strip pin number.
    array : Sequence
        Iterable of colors. Each color is either an RGB/W int or a tuple of (pixel_index, color).

    Raises
    ------
    TypeError
    ValueError
    """
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


# https://docs.python.org/3/library/struct.html#format-characters
# B: unsigned char
# L: unsigned long
# b: signed char
# ?: bool

WRGB_FORMAT = BOC + 'L'
WRGB_SIZE = struct.calcsize(WRGB_FORMAT)
AWRGB_FORMAT = BOC + 'BL'
AWRGB_SIZE = struct.calcsize(AWRGB_FORMAT)


DATA_FORMATS = {
    # New strip command. Pin is first, followed by this.
    # see setup_pixels for args.
    b'N': BOC + 'BLb?BBL',
}


def unpack_new(pin, data):
    """Unpack a new strip command.

    Parameters
    ----------
    pin : int
        Strip pin number.
    data : bytes
        Data to unpack.

    Returns
    -------
    tuple
        Unpacked tuple.
    """
    fmt = DATA_FORMATS[b'N']
    args = list(struct.unpack(fmt, data))
    args.insert(1, pin)
    return args


def unpack_addressed(data):
    """Unpack an addressed set pixel color command."""
    return struct.iter_unpack(AWRGB_FORMAT, data)


def unpack_unaddressed(data):
    """Unpack an unaddressed set pixel color command."""
    return [x[0] for x in struct.iter_unpack(WRGB_FORMAT, data) if x and len(x) == 1]


def unpack_packets(commands):
    """Unpack a command and run the appropriate action."""
    actions = unpack_packet_start([], commands)
    for action, pin, data in actions:
        a = str(action)[1:].strip('\'')  # get the command letter as a string
        print(f"{a:>3s} pin {pin: >3}: {data}")  # show the command letter, pin number, and data

        if action == b'N':  # new strip command
            args = unpack_new(pin, data)
            print(args)
            setup_pixels(*args)
        elif action == b'a':  # addressed set pixel command
            if pin not in strips:
                continue
            set_strip_int(pin, unpack_addressed(data))
        elif action == b'u':  # unaddressed set pixel command
            if pin not in strips:
                continue
            set_strip_int(pin, unpack_unaddressed(data))
        else:
            msg = f"Unknown action: {action}"
            raise ValueError(msg)


if __name__ == '__main__':
    # daemon arguments
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
    loop_read(PIPEPATH, unpack_packets)  # read lines and send them to unpack_packets
