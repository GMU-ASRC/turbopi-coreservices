# this file exists to prevent a pseudo-circular import
# caused by turbocore __init__.py importing set_buzzer

from .pindaemon import mkpipe

PIPENAME = "buzzer.pipe"
PIPEPATH = mkpipe(PIPENAME)
