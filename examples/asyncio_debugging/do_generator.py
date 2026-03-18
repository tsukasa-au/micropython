#! python

from async_debugging import print_taskqueue, print_task, get_yielded_from

def show(f, iters):
  for _ in range(iters):
    print(f'{f} -> ', end='')
    try:
      if hasattr(f, 'send'):
        print(f'{f.send(None)=}')
      else:
        print(f'{f.__next__()=}')
    except StopIteration as e:
      print(f'{e}')


def run_now(f):
  return asyncio.run(f())


def my_func():
  yield 0
  yield 1
  yield 2
  yield 3
  yield 4
  return 10

show(my_func(), iters=7)

def short_func(): yield 10

show(short_func(), iters=2)

show(iter(range(3)), iters=4)

import asyncio
import micropython
r = micropython.RingIO(10)

w_stream = asyncio.StreamWriter(r)
r_stream = asyncio.StreamReader(r)

@run_now
async def _():
  show(w_stream.drain(), iters=3)

@run_now
async def _():
  async def sleep_coro():
    await asyncio.sleep_ms(1_000)
  async def reader():
    print('Started reader')
    await r_stream.readexactly(1)
    print('Done')

  async def wait_tree(n):
    if n > 0:
      return await asyncio.create_task(wait_tree(n-1))
    await asyncio.sleep_ms(1_000)
    return n

  async def wait_tree2(n):
    if n > 0:
      return await wait_tree2(n-1)
    await asyncio.sleep_ms(1_000)
    return n

  l = asyncio.Lock()

  async def wait_locked():
    async with l:
      await asyncio.sleep_ms(1_000)

  tasks = []
  for _ in range(5):
    tasks.append(asyncio.create_task(sleep_coro()))
    tasks.append(asyncio.create_task(wait_locked()))
  r_task = asyncio.create_task(reader())
  tasks.append(asyncio.create_task(asyncio.wait_for_ms(r_task, 1_000)))
  tasks.append(asyncio.create_task(wait_tree(5)))
  tasks.append(asyncio.create_task(wait_tree2(5)))

  for _ in range(100):
    await asyncio.sleep_ms(0)
###  print_task(tasks[-1])
###  print_task(r_task)
  print()


  print_taskqueue('', asyncio.core._task_queue)

  for k, (read_t, write_t, stream) in asyncio.core._io_queue.map.items():
    print(f'{k=},{stream=}')
    if read_t:
      print_task('  ', read_t)
    if write_t:
      print_task('  ', write_t)
  print()
  print_taskqueue('', l.waiting)


  for t in tasks:
    try:
      await t
    except asyncio.TimeoutError as e:
      print(f'TimeoutErr: {e}')

@run_now
async def _():
  async def wait_tree2(n):
    if n > 0:
      return await wait_tree2(n-1)
    await asyncio.sleep_ms(1_000)
    return n

  tasks = []
  tasks.append(asyncio.create_task(wait_tree2(5)))

  for _ in range(100):
    await asyncio.sleep_ms(0)
###  print_task(tasks[-1])
###  print_task(r_task)
  print()

  print_taskqueue('', asyncio.core._task_queue)

  for k, (read_t, write_t, stream) in asyncio.core._io_queue.map.items():
    print(f'{k=},{stream=}')
    if read_t:
      print_task('  ', read_t)
    if write_t:
      print_task('  ', write_t)


  for t in tasks:
    try:
      await t
    except asyncio.TimeoutError as e:
      print(f'TimeoutErr: {e}')
