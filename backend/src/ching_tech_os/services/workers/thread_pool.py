"""共用執行緒池

將阻塞式 SMB 和文件處理操作移至執行緒池，避免阻塞 asyncio event loop。
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# SMB 操作執行緒池（I/O 密集，4 條執行緒）
_smb_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="smb")

# 文件解析執行緒池（CPU 密集，2 條執行緒）
_doc_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="doc")


async def run_in_smb_pool(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """在 SMB 執行緒池中執行阻塞式操作

    Args:
        func: 要執行的同步函式
        *args, **kwargs: 傳遞給函式的參數

    Returns:
        函式回傳值
    """
    loop = asyncio.get_running_loop()
    if kwargs:
        return await loop.run_in_executor(_smb_pool, partial(func, *args, **kwargs))
    return await loop.run_in_executor(_smb_pool, partial(func, *args) if args else func)


async def run_in_doc_pool(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """在文件解析執行緒池中執行阻塞式操作

    Args:
        func: 要執行的同步函式
        *args, **kwargs: 傳遞給函式的參數

    Returns:
        函式回傳值
    """
    loop = asyncio.get_running_loop()
    if kwargs:
        return await loop.run_in_executor(_doc_pool, partial(func, *args, **kwargs))
    return await loop.run_in_executor(_doc_pool, partial(func, *args) if args else func)


def shutdown_pools() -> None:
    """關閉所有執行緒池（應用程式關閉時呼叫）"""
    logger.info("Shutting down worker thread pools")
    _smb_pool.shutdown(wait=False)
    _doc_pool.shutdown(wait=False)
