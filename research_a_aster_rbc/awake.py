"""Scoped Windows idle-sleep prevention for an explicitly authorized run.

No global power settings are changed. Explicit user sleep remains available.
Importing this module does not request or change an execution state.
"""
from __future__ import annotations

from contextlib import contextmanager
import sys


@contextmanager
def keep_system_awake():
    """Prevent Windows idle sleep until this same-thread context exits.

    Non-Windows platforms are a no-op. Acquisition failure raises OSError before
    the body begins. Restoration failure raises OSError after a successful body;
    when the body is already raising, the restoration error is attached as a
    note so the original exception remains primary.

    Enter and exit on the same thread: SetThreadExecutionState is thread-scoped.
    This guard does not keep the display on or block explicit sleep/hibernation.
    """
    if sys.platform != 'win32':
        yield
        return

    # Delay Windows API setup until the context is entered, never at import.
    import ctypes
    from ctypes import wintypes

    es_continuous = 0x80000000
    es_system_required = 0x00000001
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    set_state = kernel32.SetThreadExecutionState
    set_state.argtypes = [wintypes.DWORD]
    set_state.restype = wintypes.DWORD

    def state_error(action):
        # This API signals failure with zero; GetLastError may be unavailable.
        code = ctypes.get_last_error()
        detail = ctypes.FormatError(code).strip() if code else 'returned zero'
        return OSError(code, f'SetThreadExecutionState {action} failed: {detail}')

    ctypes.set_last_error(0)
    previous_state = set_state(es_continuous | es_system_required)
    if not previous_state:
        raise state_error('acquisition')

    body_error = None
    try:
        yield
    except BaseException as exc:
        body_error = exc
        raise
    finally:
        # Reapply the prior continuous requirements rather than clearing a
        # pre-existing requirement belonging to this thread's outer context.
        ctypes.set_last_error(0)
        restored = set_state(previous_state | es_continuous)
        if not restored:
            error = state_error('restoration')
            if body_error is None:
                raise error
            if hasattr(body_error, 'add_note'):
                body_error.add_note(str(error))
            else:
                # Python 3.10 has no exception notes; preserve diagnostic detail
                # without replacing the experiment's original failure.
                body_error.awake_restore_error = error
