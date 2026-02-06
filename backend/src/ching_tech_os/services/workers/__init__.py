"""Worker 執行緒池模組

提供非阻塞式的 SMB 和文件處理操作。
"""

from .thread_pool import run_in_doc_pool, run_in_smb_pool, shutdown_pools

__all__ = ["run_in_smb_pool", "run_in_doc_pool", "shutdown_pools"]
