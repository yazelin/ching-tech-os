"""測試 workers/thread_pool.py 未覆蓋的分支"""

import pytest

from ching_tech_os.services.workers.thread_pool import run_in_smb_pool, run_in_doc_pool


def _add(a, b):
    return a + b


def _identity():
    return 42


class TestRunInSmb:
    @pytest.mark.asyncio
    async def test_with_kwargs(self):
        result = await run_in_smb_pool(_add, a=1, b=2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_no_args(self):
        result = await run_in_smb_pool(_identity)
        assert result == 42


class TestRunInDoc:
    @pytest.mark.asyncio
    async def test_with_kwargs(self):
        result = await run_in_doc_pool(_add, a=3, b=4)
        assert result == 7

    @pytest.mark.asyncio
    async def test_no_args(self):
        result = await run_in_doc_pool(_identity)
        assert result == 42
