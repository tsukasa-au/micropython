#! python

import asyncio
from micropython import const
import struct
import uctypes

_DEBUG_PRINT = const(False)

_MP_BC_YIELD_FROM = const((0x60) + 0x08)
PTR_SIZE = 8


_generator_type = type(lambda: (yield))
_function_type = type(lambda: None)
_closure_type = type((lambda x: (lambda: x))(None))


def _to_ptr(obj):
  if isinstance(obj, (int, str)) or obj is None:
    raise ValueError(f'_to_ptr called with non-pointer based object: {obj!r})')
  # Serialise obj to bytes, then read it back as a pointer (int)
  obj_bytes = struct.pack('@O', obj)
  obj_ptr, = struct.unpack('@P', obj_bytes)
  return obj_ptr


def _unpack_from_obj_ptr(fmt, obj_ptr):
  fmt_byte_size = struct.calcsize(fmt)
  data = uctypes.bytearray_at(obj_ptr, fmt_byte_size)
  if _DEBUG_PRINT:
    print(f'@0x{obj_ptr:08x}[:{fmt_byte_size}]=', end='')
    print(f'{data!r}')
  return struct.unpack(fmt, data)


def _unpack_from_obj(fmt, obj):
  obj_ptr = _to_ptr(obj)
  return _unpack_from_obj_ptr(fmt, obj_ptr)


def get_yielded_from(maybe_coro):
  """Get the object being yielded from in a generator.

  Inspect a suspended generator/coroutine to return the value that was passed
  to `yield from`/`await`. This only works for generators that have been
  started, but have not completed.

  Returns None:
    - if the object is not a coroutine,
    - if micropython has not been compiled with `MICROPY_PY_SYS_SETTRACE`
    - if the coroutine is not currently suspended
    - if the coroutine is suspended on some other instruction (for example
      `yield`, as opposed to `yield from`)
  """
  frame = getattr(maybe_coro, "cr_frame", None)
  if not frame:
    return
  if (instruction := frame.f_code.co_code[frame.f_lasti]) != _MP_BC_YIELD_FROM:
    return None
    raise ValueError(f'Generator not currently pointed at "yield from" instruction (got 0x{instruction:02x})')
  # Pulling code_state (struct mp_code_state_t) from struct mp_obj_frame_t.
  _frame_type, code_state_ptr = _unpack_from_obj('@OP', frame)
  assert _frame_type is type(frame)
  # Pulling ip and sp from struct mp_code_state_t
  _func_bc, ip, sp = _unpack_from_obj_ptr('@PPP', code_state_ptr)
  if not ip:
    return None
  # The MP_BC_YIELD_FROM opcode uses 2 values on the stack:
  # SP   -> object being sent into the generator (the value passed into `generator.send(...)`
  # SP-1 -> object being iterated over (the value passed to `await`/`yield from`
  yield_obj, = _unpack_from_obj_ptr('@O', sp-PTR_SIZE)
  return yield_obj


def print_task(prefix, t):
  assert isinstance(t, asyncio.Task)
  frame = t.coro.cr_frame
  print(f'{prefix}+ <Task co_name={t.coro.cr_code.co_name!r} source=\'{t.coro.cr_code.co_filename}:{frame.f_lineno}\', ph_key={t.ph_key!r}, data={t.data!r}, state={t.state!r} @0x{id(t):08x}>')
  yf_prefix = "  "

  yf = t.coro
  while yf := get_yielded_from(yf):
    frame = getattr(yf, "cr_frame", None)
    if frame:
      print(f'{prefix}{yf_prefix}- <coroutine co_name={yf.cr_code.co_name!r} source=\'{yf.cr_code.co_filename}:{frame.f_lineno}\' @0x{id(yf):08x}>')
    elif isinstance(yf, asyncio.Task):
      frame = yf.coro.cr_frame
      print(f'{prefix}{yf_prefix}- <Task co_name={yf.coro.cr_code.co_name!r} source=\'{yf.coro.cr_code.co_filename}:{frame.f_lineno}\', ph_key={yf.ph_key!r}, data={yf.data!r}, state={yf.state!r} @0x{id(yf):08x}>')
    else:
      print(f'{prefix}{yf_prefix}- {yf}')
    yf_prefix += "  "
  if isinstance(t.state, asyncio.TaskQueue):
    print_taskqueue(f'  {prefix}', t.state)


def print_taskqueue(prefix, tq):
  for t in tq:
    print_task(f'{prefix}', t)
