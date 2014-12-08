"""Greenified threading module
"""
import greenlet

from .. import patcher, event
from .. import event
from . import time, thread

threading_orig = patcher.original('threading')

__patched__ = ['_start_new_thread', '_allocate_lock', '_get_ident', '_sleep',
               'local', 'stack_size', 'Lock', 'currentThread',
               'current_thread', '_after_fork', '_shutdown', 'Event']

__threadlocal = threading_orig.local()

patcher.inject('threading', globals(), ('thread', thread), ('time', time))

Event = event.TEvent
_start_new_thread = thread.start_new_thread
_allocate_lock = thread.allocate_lock
get_ident = thread.get_ident

_count = 1


class _GreenThread:
    """Wrapper for GreenThread objects to provide Thread-like attributes and methods
    """

    def __init__(self, g):
        global _count
        self._g = g
        self._name = 'GreenThread-%d' % _count
        _count += 1

    def __repr__(self):
        return '<_GreenThread(%s, %r)>' % (self._name, self._g)

    def join(self, timeout=None):
        return self._g.wait()

    def getName(self):
        return self._name

    get_name = getName

    def setName(self, name):
        self._name = str(name)

    set_name = setName

    name = property(getName, setName)

    ident = property(lambda self: id(self._g))

    def isAlive(self):
        return True

    is_alive = isAlive

    daemon = property(lambda self: True)

    def isDaemon(self):
        return self.daemon

    is_daemon = isDaemon


__threading = None


def _fixup_thread(t):
    # Some third-party packages (lockfile) will try to patch the threading.Thread class with a
    # get_name attribute if it doesn't exist. Since we might return Thread objects from the original
    # threading package that won't get patched, let's make sure each individual object gets patched
    # to our patched threading.Thread class has been patched. This is why monkey patching can be
    # bad...
    global __threading
    if not __threading:
        __threading = __import__('threading')

    if (hasattr(__threading.Thread, 'get_name') and
            not hasattr(t, 'get_name')):
        t.get_name = t.getName
    return t


def current_thread():
    g = greenlet.getcurrent()
    if not g:
        # not currently in a greenlet, fall back to standard function
        return _fixup_thread(threading_orig.current_thread())

    try:
        active = __threadlocal.active
    except AttributeError:
        active = __threadlocal.active = {}

    try:
        t = active[id(g)]
    except KeyError:
        # Add green thread to active if we can clean it up on exit
        def cleanup(g):
            del active[id(g)]

        try:
            g.link(cleanup)
        except AttributeError:
            # Not a GreenThread type, so there's no way to hook into
            # the green thread exiting. Fall back to the standard
            # function then.
            t = _fixup_thread(threading_orig.currentThread())
        else:
            t = active[id(g)] = _GreenThread(g)

    return t


currentThread = current_thread
