"""voice 模組啟動/關閉"""

from __future__ import annotations

import logging

logger = logging.getLogger("voice.startup")


async def startup() -> None:
    """模組啟動：預載 whisper 模型"""
    logger.info("voice 模組啟動中...")
    from voice_stt import warmup
    await warmup()
    logger.info("voice 模組啟動完成")


async def shutdown() -> None:
    """模組關閉：釋放資源"""
    from voice_stt import cleanup
    cleanup()
    logger.info("voice 模組已關閉")
