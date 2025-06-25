import asyncio
from functools import wraps

def await_async_tool(async_fn):
    @wraps(async_fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(async_fn(*args, **kwargs))
    return wrapper
