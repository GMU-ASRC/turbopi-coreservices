import os
import struct


from .rgbd import DATA_FORMATS, AWRGB_FORMAT, WRGB_FORMAT, PIPEPATH
from . import rgbd
from .pindaemon import write_pin_cmd


def rgbw_to_int(r, g, b, w=0):
    """Pack 8-bit r, g, b, w(optional) values into an integer

    Each r, g, b, w should be in the range 0-255.

    Parameters
    ----------
    r : int
    g : int
    b : int
    w : int, optional

    Returns
    -------
    int
    """
    return int.from_bytes(struct.pack('>BBBB', w, r, g, b), byteorder='big')


def set_pixel(pin, i, r=0, g=None, b=None, w=None):
    """Command the daemon to set a single pixel color and update the strip.

    You can either provide a single integer for the color, or three separate
    integers for r, g, and b.

    Parameters
    ----------
    pin : int
        Pin number of the strip.
    i : int
        Pixel number in the strip.
    r : int, optional
    g : int, optional
    b : int, optional
    w : int, optional

    Raises
    ------
    NotImplementedError
        raised if w is not None
    ValueError
    """
    CMD = b'S'
    if (g, b, w) == (None, None, None):
        rgb = r
        if isinstance(rgb, bytes):
            rgb = int.from_bytes(rgb, byteorder='big')
    elif all(isinstance(x, int) for x in (r, g, b)):
        if w is not None:
            raise NotImplementedError("RGBW white channel not implemented yet.")
        w = 0 if w is None else w
        rgb = rgbw_to_int(r, g, b, w)
    else:
        raise ValueError
    write_pin_cmd(PIPEPATH, pin, CMD, struct.pack(AWRGB_FORMAT, i, rgb))


def set_pixels(pin, array):
    """Command the daemon to set the color of multiple pixels and update the strip.

    Four array formats are supported:
    1. [(i, rgbw_int), ...]
    2. [(i, (r, g, b, [w])), ...]
    3. [(r, g, b, [w]), ...]
    4. [rgbw_int, ...]

    Parameters
    ----------
    pin : int
        Pin number of the strip.
    array : Sequence
        Iterable of colors. Each color is either an RGB/W int or a tuple of (pixel_index, color).

    Raises
    ------
    TypeError
        raised if type(array) is not in (tuple, list)
    ValueError
        raised if all elements of array are not in (int, tuple)

    Examples
    --------
    >>> # these are all equivalent commands to set the two pixels to [red, green]
    >>> set_pixels(12, [(0, 0xFF0000), (1, 0x00FF00)])
    >>> set_pixels(12, [(0, (255, 0, 0)), (1, (0, 255, 0))])
    >>> set_pixels(12, [(255, 0, 0), (0, 255, 0)])
    >>> set_pixels(12, [0xFF0000, 0x00FF00])
    """

    cmd = b'a'  # for addressed
    if all(isinstance(obj, int) for obj in array):  # case 4
        cmd = b'u'  # for unaddressed
    elif all(3 <= len(pix) <= 4 for pix in array):  # case 3
        cmd = b'u'  # for unaddressed
        array = [rgbw_to_int(*pix) for pix in array]
    elif all(isinstance(obj[1], (tuple, list)) for obj in array):
        array = [(i, rgbw_to_int(*rgbw)) for i, rgbw in array]
    if cmd == b'a':
        data = b''.join(struct.pack(AWRGB_FORMAT, i, rgb_int) for i, rgb_int in array)
    else:
        data = b''.join(struct.pack(WRGB_FORMAT, rgb_int) for rgb_int in array)
    write_pin_cmd(PIPEPATH, pin, cmd, data)


def setup(
    pin: int,
    num_leds: int,
    freq_hz: int = 800000,
    dma: int = 10,
    invert: bool = False,
    brightness: int = 120,
    channel: int = 0,
    strip_type: int = rgbd.WS2811_STRIP_GRB,
):
    """Command the daemon to setup a strip object.

    .. danger::
        Setting the wrong DMA channel may brick your Pi or SD card.
        See https://github.com/jgarff/rpi_ws281x#important-warning-about-dma-channels

    Parameters
    ----------
    pin : int
        Pin number of the strip.
    num_leds : int
        Number of LEDs on the strip.
    freq_hz : int, default=800000
    dma : int, default=10
    invert : bool, default=False
    brightness : int, default=120
    channel : int, default=0
    strip_type : int, default=rgbd.WS2811_STRIP_GRB
    """
    cmd = b'N'
    fmts = DATA_FORMATS[cmd]
    data = (num_leds, freq_hz, dma, invert, brightness, channel, strip_type)
    strip = struct.pack(fmts, *data)
    write_pin_cmd(PIPEPATH, pin, cmd, strip)


def setup_default_pixels(
    n=2,
    pin=12,
    f=800000,
    dma_channel=10,
    brightness=120,
    channel=0,
    invert=False,
):
    """Convenience command to setup the rasadapter's built-in two neopixels."""
    setup(pin, n, f, dma_channel, invert, brightness, channel)
