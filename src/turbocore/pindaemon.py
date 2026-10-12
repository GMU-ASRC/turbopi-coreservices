import os
import stat
import struct
from tempfile import gettempdir

from typing import Callable

ISNT = os.name == 'nt'
ISROOT = not ISNT and os.geteuid() == 0


BYTEORDER = 'little'
BOC = '<' if BYTEORDER == 'little' else '>'  # byte order character for struct
# packet format: (header)[, binary data]
# (cmd, pin, datasize)[, data]
HEADER_FORMAT = BOC + f'shH'  # char, short, ushort (short is 2 bytes)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

#
# client/lib
#


def cannot_write_pipe(path):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        from warnings import warn
        warn(f"pipe {path} couldn't be opened."
             " Is the service running? check w/ journalctl --unit rgbd",
             RuntimeWarning, 3)
        return True
    finally:
        try:
            os.close(fd)
        except (NameError, OSError):
            pass


def write_pin_cmd(path: str | os.PathLike, pin: int, cmd: bytes, data=b''):
    header = struct.pack(HEADER_FORMAT, cmd, pin, len(data))
    packet = header + data
    if cannot_write_pipe(path):
        raise IOError('cannot write to pipe')
    with open(path, 'wb') as pipe:
        return pipe.write(packet)


#
# daemon
#


def mkpipe(name: str | os.PathLike):
    directory = gettempdir()
    path = os.path.join(directory, name)

    if not ISNT:
        os.makedirs(os.path.dirname(path), exist_ok=True)  # ensure that /tmp/ exists

    if os.path.exists(path):
        is_fifo = os.stat(path).st_mode & stat.S_IFIFO
        # if path is not pipe, remove it
        if ISROOT:
            if not is_fifo:
                os.unlink(path)
                os.mkfifo(path, mode=0o666)
            os.chmod(path, 0o666)
    elif ISROOT:
        os.mkfifo(path, mode=0o666)
        os.chmod(path, 0o666)
    return path


def unpack_packet_start(actions, remainder, size_limit=2000):
    header = remainder[:HEADER_SIZE]
    remainder = remainder[HEADER_SIZE:]
    if len(header) != HEADER_SIZE:
        # not enough data to continue. bail out.
        return actions
    action, pin, size = struct.unpack(HEADER_FORMAT, header)
    packed_data = remainder[:size]
    remainder = remainder[size:]
    if len(packed_data) < size or size > size_limit:
        # packet is lying/incomplete. Possible corruption.
        return actions
    actions.append((action, pin, packed_data))
    if remainder:
        return unpack_packet_start(actions, remainder, size_limit)
    else:
        return actions


def loop_read(path: str | os.PathLike, func: Callable):
    i = 0
    with open(path, "rb") as pipe:
        while True:
            try:
                data = pipe.read()
                if data:
                    print(f"{i: >3}: {data}")
                    func(data)
            # except struct.error as err:
            # except TypeError as err:
            except Exception as e:
                print(e)
            i += 1
