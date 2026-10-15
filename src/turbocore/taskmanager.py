import os
import json
import pathlib as pl

# typing
import typing
from typing import Any

try:
    import psutil
    from psutil import Process
except (ImportError, ModuleNotFoundError):
    if not typing.TYPE_CHECKING:
        psutil = None
        Process = None


PID_DIR = "/tmp/buttonman"


class ProcessMismatchError(Exception):
    pass


class TaskManager:
    def __init__(self, pid_dir=None):
        self.pid = os.getpid()
        self.pid_dir = pl.Path(PID_DIR)

        if pid_dir is None:
            pid_dir = PID_DIR
        listing_path = pl.Path(pid_dir)
        listing_path.mkdir(parents=False, exist_ok=True)  # raise error if /tmp does not exist
        try:
            listing_path.chmod(0o777)
        except PermissionError:
            pass

    @staticmethod
    def process_dict_excerpt(p: psutil.Process):
        if isinstance(p, int):
            p = psutil.Process(p)
        with p.oneshot():
            return {
                'pid': p.pid,
                'name': p.name(),
                'username': p.username(),
                'cmdline': p.cmdline(),
                'create_time': p.create_time()
            }

    @classmethod
    def register_stoppable(cls, pid_dir=None):
        # Run this from within your program to register it to buttonman.
        if pid_dir is None:
            pid_dir = PID_DIR
        listing_path = pl.Path(pid_dir)
        listing_path.mkdir(parents=False, exist_ok=True)  # raise error if /tmp does not exist
        try:
            listing_path.chmod(0o777)
        except PermissionError:
            pass
        # Note: /tmp is probably guaranteed to exist on POSIX, but sysadmins may choose a different $TMPDIR.
        # See both top answers here: https://unix.stackexchange.com/questions/362100/is-tmp-guaranteed-to-exist
        # We're targeting Raspberry Pi though so who cares.
        pid = os.getpid()
        self_infofile = listing_path / f'{pid}'
        selfp = psutil.Process(pid)
        with selfp.oneshot():
            info = cls.process_dict_excerpt(selfp)
        info_str = json.dumps(info) + '\n'
        # equivalent to opening in 'w' mode; writing; closing.
        self_infofile.write_text(info_str)  # OVERWRITES EXISTING!
        self_infofile.chmod(0o777)

    @classmethod
    def unregister(cls, pid_dir=None, check_match=True):
        # Run this from within your program to unregister it from buttonman.
        # Only deletes file if it matches the current process info.
        if pid_dir is None:
            pid_dir = PID_DIR
        listing_path = pl.Path(pid_dir)
        pid = os.getpid()
        infofile = listing_path / f'{pid}'
        record = cls.read_record(infofile)
        if (not check_match
            or cls.pid_matches_process(pid, record)):
            infofile.unlink(missing_ok=True)

    @classmethod
    def pid_matches_process(cls, pid, pid_info):
        if not isinstance(pid_info, dict):
            return None
        # return process if match, else None
        try:
            actual_process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return None
        with actual_process.oneshot():
            actual_process_info = cls.process_dict_excerpt(actual_process)
        # for compatibility with programs that don't have access to psutil
        if 'cmdline' not in pid_info or 'create_time' not in pid_info:
            pid_info.pop('cmdline', None)
            pid_info.pop('create_time', None)
            actual_process_info.pop('cmdline')
            actual_process_info.pop('create_time')
        if actual_process_info == pid_info:
            return actual_process

    @staticmethod
    def read_record(path):
        path = pl.Path(path)
        # try to load the record as dict from json
        try:
            txt: str = path.read_text()
            record: dict[str, Any] = json.loads(txt)
            return record
        except json.JSONDecodeError as err:
            return err
        except FileNotFoundError as err:
            return err

    def close_registered(self, pid: int, timeout=5, ignore_nonexistent=False):
        # attempt to close the process if it matches its registration.
        # Can return FileNotFoundError, JSONDecodeError
        # If timeout is positive, then it will wait for the process to terminate, and will be killed if the timeout elapses.
        # Otherwise, termination will only be attempted and the process will be returned so you can check on it.
        # If ignore_nonexistent is False (default), FileNotFoundError is RAISED if the process record can't be found.
        # All other errors are raised.
        # If the process is terminated successfully, the return code or -signal is returned. (see comment below)
        fpath = self.pid_dir / str(pid)
        if not fpath.exists() and ignore_nonexistent:
            try:
                open(fpath)
            except FileNotFoundError as err:
                return err

        def delete_record():
            fpath.unlink(missing_ok=True)

        record = self.read_record(fpath)  # may return error

        if (process := self.pid_matches_process(pid, record)):  # Falsy if error retrieving record
            try:
                process.terminate()  # ask nicely
            except psutil.AccessDenied as err:
                print(err)
                return err
            # if timeout is valid, BLOCK, wait, and then kill.
            if isinstance(timeout, (float, int)) and timeout > 0:
                try:
                    result = process.wait(timeout=timeout)
                except psutil.TimeoutExpired:
                    result = process.kill()  # not asking nicely anymore
                delete_record()
                return result  # https://psutil.readthedocs.io/en/latest/#psutil.Process.wait
            else:  # if no timeout, return immediately.
                return process, fpath
        else:
            delete_record()
            return ProcessMismatchError(f"Process does not match stored process registration record. Process not terminated. pid: {pid}")  # noqa: E501

    def close_all_registered(self, processes=1):
        attempts = []
        for child in self.pid_dir.iterdir():
            # exclude directories and .dotfiles
            if not child.is_file() or child.name.startswith('.'):
                continue
            # exclude file names that don't look like ints
            try:
                pid = float(child.name)
                if pid == int(pid):
                    pid = int(pid)
                else:
                    raise ValueError
            except ValueError:
                continue
            # attempt to terminate.
            attempts.append(self.close_registered(pid, timeout=-1))
        results = [x for x in attempts if isinstance(x, tuple)]
        processes = [process for process, _path in results]
        # force kill the remaining ones.
        gone, alive = psutil.wait_procs(processes, timeout=10)
        for process, path in results:
            if process in alive:
                process.kill()
            path.unlink(missing_ok=True)
        return gone, alive

    def clean_start(self):

        self.close_all_registered()
