"""Core firmware API: libc, records, mutexes, queues, timers, strings, storage."""
from __future__ import annotations

import random
import struct
import time

from ..machine import Yield
from . import (FuriStatusErrorParameter, FuriStatusErrorResource,
               FuriStatusErrorTimeout, FuriStatusOk, FuriWaitForever, api,
               format_c, s32)

# --------------------------------------------------------------------------
# libc
# --------------------------------------------------------------------------


@api("malloc", 1)
def _malloc(env, size):
    if size == 0:
        size = 1
    addr = env.machine.heap.alloc(size)
    env.machine.write(addr, b"\x00" * size)     # firmware zeroes allocations
    return addr


@api("free", 1)
def _free(env, ptr):
    if ptr:
        env.machine.heap.free(ptr)


@api("realloc", 2)
def _realloc(env, ptr, size):
    m = env.machine
    if not ptr:
        return _malloc(env, size)
    if size == 0:
        m.heap.free(ptr)
        return 0
    old = m.heap.size_of(ptr)
    new = m.heap.alloc(size)
    m.write(new, b"\x00" * size)
    if old:
        m.write(new, m.read(ptr, min(old, size)))
    m.heap.free(ptr)
    return new


@api("calloc", 2)
def _calloc(env, count, size):
    return _malloc(env, max(1, count * size))


@api("memset", 3)
def _memset(env, dst, value, size):
    if size:
        env.machine.write(dst, bytes([value & 0xFF]) * size)
    return dst


@api("memcpy", 3)
def _memcpy(env, dst, src, size):
    if size:
        env.machine.write(dst, env.machine.read(src, size))
    return dst


@api("memmove", 3)
def _memmove(env, dst, src, size):
    return _memcpy(env, dst, src, size)


@api("memcmp", 3)
def _memcmp(env, a, b, size):
    if not size:
        return 0
    da, db = env.machine.read(a, size), env.machine.read(b, size)
    return 0 if da == db else (1 if da > db else -1)


@api("strlen", 1)
def _strlen(env, ptr):
    return len(env.machine.cstring(ptr))


@api("strcmp", 2)
def _strcmp(env, a, b):
    sa, sb = env.machine.cstring(a), env.machine.cstring(b)
    return 0 if sa == sb else (1 if sa > sb else -1)


@api("strncmp", 3)
def _strncmp(env, a, b, n):
    sa, sb = env.machine.cstring(a)[:n], env.machine.cstring(b)[:n]
    return 0 if sa == sb else (1 if sa > sb else -1)


@api("strcpy", 2)
def _strcpy(env, dst, src):
    env.machine.write(dst, env.machine.cstring(src).encode() + b"\x00")
    return dst


@api("strchr", 2)
def _strchr(env, ptr, ch):
    text = env.machine.cstring(ptr)
    pos = text.find(chr(ch & 0xFF))
    return ptr + pos if pos >= 0 else 0


@api("rand", 0)
def _rand(env):
    return random.randint(0, 0x7FFFFFFF)


@api("srand", 1)
def _srand(env, seed):
    random.seed(seed)


@api("abs", 1)
def _abs(env, v):
    return abs(s32(v))


@api("__errno", 0)
def _errno(env):
    return env.errno_ptr


@api("abort", 0)
def _abort(env):
    env.request_exit("app called abort()")
    return Yield("exit", {})


@api("__furi_crash_implementation", 0)
def _crash(env):
    env.request_exit("app called furi_crash()")
    return Yield("exit", {})


@api("__wrap_snprintf", 3)
def _snprintf(env, buf, size, fmt):
    text = format_c(env, env.machine.cstring(fmt), 3)
    data = text.encode("utf-8")[:max(0, size - 1)] + b"\x00" if size else b""
    if size:
        env.machine.write(buf, data)
    return len(text)


@api("__wrap_sniprintf", 3)
def _sniprintf(env, buf, size, fmt):
    return _snprintf(env, buf, size, fmt)


@api("__wrap_strtof", 2)
def _strtof(env, ptr, endptr):
    text = env.machine.cstring(ptr).strip()
    acc = ""
    for ch in text:
        if ch.isdigit() or ch in "+-.eE":
            acc += ch
        else:
            break
    try:
        value = float(acc)
    except ValueError:
        value = 0.0
    if endptr:
        env.machine.put_u32(endptr, ptr + len(acc))
    return struct.unpack("<I", struct.pack("<f", value))[0]


# --------------------------------------------------------------------------
# furi core
# --------------------------------------------------------------------------


@api("furi_record_open", 1)
def _record_open(env, name_ptr):
    return env.record(env.machine.cstring(name_ptr))


@api("furi_record_close", 1)
def _record_close(env, name_ptr):
    return None


@api("furi_log_print_format", 3)
def _log(env, level, tag, fmt):
    text = format_c(env, env.machine.cstring(fmt), 3)
    env.log(f"[{env.machine.cstring(tag)}] {text}")


@api("furi_log_print_raw_format", 2)
def _log_raw(env, level, fmt):
    env.log(format_c(env, env.machine.cstring(fmt), 2))


@api("furi_kernel_get_tick_frequency", 0)
def _tick_freq(env):
    return 1000


@api("furi_get_tick", 0)
def _get_tick(env):
    return env.now_ms()


@api("furi_kernel_get_tick_count", 0)
def _tick_count(env):
    return env.now_ms()


@api("furi_delay_ms", 1)
def _delay_ms(env, ms):
    return Yield("delay", {"until": env.now_ms() + ms})


@api("furi_delay_us", 1)
def _delay_us(env, us):
    if us >= 2000:
        return Yield("delay", {"until": env.now_ms() + us // 1000})
    return None


@api("furi_delay_tick", 1)
def _delay_tick(env, ticks):
    return _delay_ms(env, ticks)


# --- mutex (single-threaded emulation, so these always succeed) -------------
class Mutex:
    __slots__ = ("locked",)

    def __init__(self):
        self.locked = False


@api("furi_mutex_alloc", 1)
def _mutex_alloc(env, mtype):
    return env.machine.new_handle(Mutex())


@api("furi_mutex_free", 1)
def _mutex_free(env, handle):
    env.machine.drop_handle(handle)


@api("furi_mutex_acquire", 2)
def _mutex_acquire(env, handle, timeout):
    mutex = env.machine.handle(handle)
    if mutex is None:
        return FuriStatusErrorParameter
    mutex.locked = True
    return FuriStatusOk


@api("furi_mutex_release", 1)
def _mutex_release(env, handle):
    mutex = env.machine.handle(handle)
    if mutex is None:
        return FuriStatusErrorParameter
    mutex.locked = False
    return FuriStatusOk


# --- message queue ----------------------------------------------------------
class MessageQueue:
    def __init__(self, capacity: int, msg_size: int):
        self.capacity = capacity
        self.msg_size = msg_size
        self.items = []

    def put(self, data: bytes) -> bool:
        if len(self.items) >= self.capacity:
            return False
        self.items.append(data)
        return True

    def get(self):
        return self.items.pop(0) if self.items else None


@api("furi_message_queue_alloc", 2)
def _mq_alloc(env, capacity, msg_size):
    return env.machine.new_handle(MessageQueue(capacity, msg_size))


@api("furi_message_queue_free", 1)
def _mq_free(env, handle):
    env.machine.drop_handle(handle)


@api("furi_message_queue_put", 3)
def _mq_put(env, handle, msg_ptr, timeout):
    queue = env.machine.handle(handle)
    if not isinstance(queue, MessageQueue):
        return FuriStatusErrorParameter
    data = env.machine.read(msg_ptr, queue.msg_size) if msg_ptr else b"\x00" * queue.msg_size
    return FuriStatusOk if queue.put(bytes(data)) else FuriStatusErrorResource


@api("furi_message_queue_get", 3)
def _mq_get(env, handle, out_ptr, timeout):
    queue = env.machine.handle(handle)
    if not isinstance(queue, MessageQueue):
        return FuriStatusErrorParameter
    data = queue.get()
    if data is not None:
        if out_ptr:
            env.machine.write(out_ptr, data)
        return FuriStatusOk
    if timeout == 0:
        return FuriStatusErrorResource
    # Nothing queued: park the app so the host can render and gather input.
    deadline = None if timeout == FuriWaitForever else env.now_ms() + timeout
    return Yield("queue_get", {"queue": queue, "out": out_ptr, "deadline": deadline},
                 fallback=FuriStatusErrorResource)


@api("furi_message_queue_get_count", 1)
def _mq_count(env, handle):
    queue = env.machine.handle(handle)
    return len(queue.items) if isinstance(queue, MessageQueue) else 0


@api("furi_message_queue_reset", 1)
def _mq_reset(env, handle):
    queue = env.machine.handle(handle)
    if isinstance(queue, MessageQueue):
        queue.items.clear()
    return FuriStatusOk


# --- timers -----------------------------------------------------------------
class Timer:
    def __init__(self, callback: int, ttype: int, context: int):
        self.callback = callback
        self.periodic = ttype == 1
        self.context = context
        self.running = False
        self.period = 0
        self.next_due = 0


@api("furi_timer_alloc", 3)
def _timer_alloc(env, callback, ttype, context):
    timer = Timer(callback, ttype, context)
    handle = env.machine.new_handle(timer)
    env.timers.append(timer)
    return handle


@api("furi_timer_free", 1)
def _timer_free(env, handle):
    timer = env.machine.handle(handle)
    if isinstance(timer, Timer):
        timer.running = False
        if timer in env.timers:
            env.timers.remove(timer)
    env.machine.drop_handle(handle)


@api("furi_timer_start", 2)
def _timer_start(env, handle, period):
    timer = env.machine.handle(handle)
    if not isinstance(timer, Timer):
        return FuriStatusErrorParameter
    timer.period = max(1, period)
    timer.running = True
    timer.next_due = env.now_ms() + timer.period
    return FuriStatusOk


@api("furi_timer_stop", 1)
def _timer_stop(env, handle):
    timer = env.machine.handle(handle)
    if isinstance(timer, Timer):
        timer.running = False
    return FuriStatusOk


@api("furi_timer_is_running", 1)
def _timer_running(env, handle):
    timer = env.machine.handle(handle)
    return 1 if isinstance(timer, Timer) and timer.running else 0


@api("furi_timer_set_thread_priority", 1)
def _timer_prio(env, prio):
    return None


# --- threads ----------------------------------------------------------------
class Thread:
    def __init__(self):
        self.callback = 0
        self.context = 0
        self.name = ""
        self.ret = 0


@api("furi_thread_alloc", 0)
def _thread_alloc(env):
    return env.machine.new_handle(Thread())


@api("furi_thread_alloc_ex", 4)
def _thread_alloc_ex(env, name, stack, callback, context):
    thread = Thread()
    thread.name = env.machine.cstring(name)
    thread.callback = callback
    thread.context = context
    return env.machine.new_handle(thread)


@api("furi_thread_free", 1)
def _thread_free(env, handle):
    env.machine.drop_handle(handle)


@api("furi_thread_set_callback", 2)
def _thread_cb(env, handle, callback):
    thread = env.machine.handle(handle)
    if isinstance(thread, Thread):
        thread.callback = callback


@api("furi_thread_set_context", 2)
def _thread_ctx(env, handle, context):
    thread = env.machine.handle(handle)
    if isinstance(thread, Thread):
        thread.context = context


@api("furi_thread_set_name", 2)
def _thread_name(env, handle, name):
    thread = env.machine.handle(handle)
    if isinstance(thread, Thread):
        thread.name = env.machine.cstring(name)


@api("furi_thread_set_stack_size", 2)
def _thread_stack(env, handle, size):
    return None


@api("furi_thread_start", 1)
def _thread_start(env, handle):
    """Run the thread body inline.

    There is no scheduler here, so a spawned thread runs to completion at the
    point it is started. That suits worker threads that do a unit of work; a
    thread that loops forever would not return control, so it is capped.
    """
    thread = env.machine.handle(handle)
    if isinstance(thread, Thread) and thread.callback:
        env.log(f"running thread '{thread.name or 'unnamed'}' inline")
        thread.ret = env.machine.call(thread.callback, [thread.context])


@api("furi_thread_join", 1)
def _thread_join(env, handle):
    return 1


@api("furi_thread_get_return_code", 1)
def _thread_ret(env, handle):
    thread = env.machine.handle(handle)
    return thread.ret if isinstance(thread, Thread) else 0


# --- FuriString -------------------------------------------------------------
class FuriString:
    def __init__(self, text: str = ""):
        self.text = text
        self.buf = 0          # lazily materialised C string

    def invalidate(self):
        self.buf = 0


def _string_obj(env, handle):
    obj = env.machine.handle(handle)
    return obj if isinstance(obj, FuriString) else None


@api("furi_string_alloc", 0)
def _fs_alloc(env):
    return env.machine.new_handle(FuriString())


@api("furi_string_alloc_set_str", 1)
def _fs_alloc_set(env, ptr):
    return env.machine.new_handle(FuriString(env.machine.cstring(ptr)))


@api("furi_string_alloc_printf", 1)
def _fs_alloc_printf(env, fmt):
    return env.machine.new_handle(
        FuriString(format_c(env, env.machine.cstring(fmt), 1)))


@api("furi_string_free", 1)
def _fs_free(env, handle):
    env.machine.drop_handle(handle)


@api("furi_string_reset", 1)
def _fs_reset(env, handle):
    s = _string_obj(env, handle)
    if s:
        s.text = ""
        s.invalidate()


@api("furi_string_set_str", 2)
def _fs_set(env, handle, ptr):
    s = _string_obj(env, handle)
    if s:
        s.text = env.machine.cstring(ptr)
        s.invalidate()


@api("furi_string_printf", 2)
def _fs_printf(env, handle, fmt):
    s = _string_obj(env, handle)
    if s:
        s.text = format_c(env, env.machine.cstring(fmt), 2)
        s.invalidate()
    return 0


@api("furi_string_cat_printf", 2)
def _fs_cat_printf(env, handle, fmt):
    s = _string_obj(env, handle)
    if s:
        s.text += format_c(env, env.machine.cstring(fmt), 2)
        s.invalidate()
    return 0


@api("furi_string_cat_str", 2)
def _fs_cat_str(env, handle, ptr):
    s = _string_obj(env, handle)
    if s:
        s.text += env.machine.cstring(ptr)
        s.invalidate()


@api("furi_string_push_back", 2)
def _fs_push(env, handle, ch):
    s = _string_obj(env, handle)
    if s:
        s.text += chr(ch & 0xFF)
        s.invalidate()


@api("furi_string_size", 1)
def _fs_size(env, handle):
    s = _string_obj(env, handle)
    return len(s.text.encode("utf-8")) if s else 0


@api("furi_string_empty", 1)
def _fs_empty(env, handle):
    s = _string_obj(env, handle)
    return 1 if (s is None or not s.text) else 0


@api("furi_string_get_cstr", 1)
def _fs_cstr(env, handle):
    s = _string_obj(env, handle)
    if not s:
        return env.empty_string
    if not s.buf:
        s.buf = env.machine.alloc_cstring(s.text)
    return s.buf


# --------------------------------------------------------------------------
# storage (backed by a real folder on the host)
# --------------------------------------------------------------------------
class HostFile:
    def __init__(self):
        self.fh = None
        self.error = 0

    def close(self):
        if self.fh:
            try:
                self.fh.close()
            except OSError:
                pass
            self.fh = None


@api("storage_file_alloc", 1)
def _file_alloc(env, storage):
    return env.machine.new_handle(HostFile())


@api("storage_file_free", 1)
def _file_free(env, handle):
    f = env.machine.handle(handle)
    if isinstance(f, HostFile):
        f.close()
    env.machine.drop_handle(handle)


@api("storage_file_open", 4)
def _file_open(env, handle, path_ptr, access, mode):
    f = env.machine.handle(handle)
    if not isinstance(f, HostFile):
        return 0
    path = env.host_path(env.machine.cstring(path_ptr))
    # FS_AccessMode: Read=1, Write=2, ReadWrite=3
    want_write = bool(access & 2)
    try:
        if want_write:
            path.parent.mkdir(parents=True, exist_ok=True)
            f.fh = open(path, "r+b" if path.exists() and (access & 1) else "wb")
        else:
            f.fh = open(path, "rb")
        return 1
    except OSError:
        f.error = 1
        return 0


@api("storage_file_close", 1)
def _file_close(env, handle):
    f = env.machine.handle(handle)
    if isinstance(f, HostFile):
        f.close()
    return 1


@api("storage_file_read", 3)
def _file_read(env, handle, buf, size):
    f = env.machine.handle(handle)
    if not isinstance(f, HostFile) or not f.fh:
        return 0
    data = f.fh.read(size)
    if data:
        env.machine.write(buf, data)
    return len(data)


@api("storage_file_write", 3)
def _file_write(env, handle, buf, size):
    f = env.machine.handle(handle)
    if not isinstance(f, HostFile) or not f.fh:
        return 0
    f.fh.write(env.machine.read(buf, size))
    return size


@api("storage_file_seek", 3)
def _file_seek(env, handle, offset, from_start):
    f = env.machine.handle(handle)
    if not isinstance(f, HostFile) or not f.fh:
        return 0
    f.fh.seek(offset, 0 if from_start else 1)
    return 1


@api("storage_file_tell", 1)
def _file_tell(env, handle):
    f = env.machine.handle(handle)
    return f.fh.tell() if isinstance(f, HostFile) and f.fh else 0


@api("storage_file_size", 1)
def _file_size(env, handle):
    f = env.machine.handle(handle)
    if not isinstance(f, HostFile) or not f.fh:
        return 0
    here = f.fh.tell()
    f.fh.seek(0, 2)
    size = f.fh.tell()
    f.fh.seek(here)
    return size


@api("storage_file_eof", 1)
def _file_eof(env, handle):
    f = env.machine.handle(handle)
    if not isinstance(f, HostFile) or not f.fh:
        return 1
    here = f.fh.tell()
    f.fh.seek(0, 2)
    end = f.fh.tell()
    f.fh.seek(here)
    return 1 if here >= end else 0


@api("storage_file_get_error", 1)
def _file_error(env, handle):
    f = env.machine.handle(handle)
    return f.error if isinstance(f, HostFile) else 0


@api("storage_common_stat", 3)
def _common_stat(env, storage, path_ptr, info_ptr):
    path = env.host_path(env.machine.cstring(path_ptr))
    if not path.exists():
        return 2  # FSE_NOT_EXIST
    if info_ptr:
        flags = 1 if path.is_dir() else 0
        env.machine.put_u32(info_ptr, flags)
        env.machine.put_u32(info_ptr + 4, 0 if path.is_dir() else path.stat().st_size)
    return 0


@api("storage_simply_mkdir", 2)
def _mkdir(env, storage, path_ptr):
    try:
        env.host_path(env.machine.cstring(path_ptr)).mkdir(parents=True, exist_ok=True)
        return 1
    except OSError:
        return 0


@api("storage_file_exists", 2)
def _file_exists(env, storage, path_ptr):
    return 1 if env.host_path(env.machine.cstring(path_ptr)).exists() else 0
