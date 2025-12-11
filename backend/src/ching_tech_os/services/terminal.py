"""終端機 PTY 管理服務"""

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

import ptyprocess


@dataclass
class TerminalSession:
    """單一終端機 session"""

    session_id: str
    pty: ptyprocess.PtyProcess
    user_id: Optional[int] = None
    websocket_sid: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    _read_task: Optional[asyncio.Task] = field(default=None, repr=False)
    _output_callback: Optional[Callable[[str, bytes], None]] = field(default=None, repr=False)

    def write(self, data: str) -> None:
        """寫入資料到 PTY stdin"""
        self.last_activity = datetime.now()
        self.pty.write(data.encode('utf-8'))

    def resize(self, rows: int, cols: int) -> None:
        """調整 PTY 視窗大小"""
        self.pty.setwinsize(rows, cols)

    def get_cwd(self) -> Optional[str]:
        """取得 PTY 當前工作目錄"""
        try:
            pid = self.pty.pid
            cwd = os.readlink(f'/proc/{pid}/cwd')
            return cwd
        except (OSError, FileNotFoundError):
            return None

    def close(self) -> None:
        """關閉 PTY session"""
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
        if self.pty.isalive():
            self.pty.terminate(force=True)

    async def start_reading(self, callback: Callable[[str, bytes], None]) -> None:
        """開始非同步讀取 PTY 輸出"""
        self._output_callback = callback
        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        """PTY 輸出讀取迴圈"""
        loop = asyncio.get_event_loop()
        try:
            while self.pty.isalive():
                try:
                    # 使用 executor 避免阻塞
                    data = await loop.run_in_executor(
                        None,
                        lambda: self.pty.read(4096)
                    )
                    if data and self._output_callback:
                        await self._output_callback(self.session_id, data)
                except EOFError:
                    break
                except Exception:
                    break
        except asyncio.CancelledError:
            pass


class TerminalService:
    """終端機服務 - 管理所有 PTY sessions"""

    SESSION_TIMEOUT = timedelta(minutes=5)
    CLEANUP_INTERVAL = 60  # 秒

    def __init__(self):
        self._sessions: dict[str, TerminalSession] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._output_callback: Optional[Callable[[str, bytes], None]] = None

    def set_output_callback(self, callback: Callable[[str, bytes], None]) -> None:
        """設定輸出回呼函式"""
        self._output_callback = callback

    async def create_session(
        self,
        websocket_sid: str,
        user_id: Optional[int] = None,
        cols: int = 80,
        rows: int = 24
    ) -> TerminalSession:
        """建立新的終端機 session"""
        session_id = str(uuid.uuid4())

        # 取得 shell
        shell = os.environ.get('SHELL', '/bin/bash')

        # 取得終端機起始目錄 (預設為使用者家目錄)
        terminal_cwd = os.environ.get('TERMINAL_CWD', os.path.expanduser('~'))

        # 建立 PTY process
        pty = ptyprocess.PtyProcess.spawn(
            [shell],
            cwd=terminal_cwd,
            dimensions=(rows, cols),
            env={
                **os.environ,
                'TERM': 'xterm-256color',
                'COLORTERM': 'truecolor',
            }
        )

        session = TerminalSession(
            session_id=session_id,
            pty=pty,
            user_id=user_id,
            websocket_sid=websocket_sid,
        )

        self._sessions[session_id] = session

        # 開始讀取輸出
        if self._output_callback:
            await session.start_reading(self._output_callback)

        return session

    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        """取得 session"""
        return self._sessions.get(session_id)

    def get_session_by_websocket(self, websocket_sid: str) -> list[TerminalSession]:
        """根據 WebSocket SID 取得所有 sessions"""
        return [
            s for s in self._sessions.values()
            if s.websocket_sid == websocket_sid
        ]

    def close_session(self, session_id: str) -> bool:
        """關閉並移除 session"""
        session = self._sessions.pop(session_id, None)
        if session:
            session.close()
            return True
        return False

    def detach_websocket(self, websocket_sid: str) -> list[str]:
        """WebSocket 斷線時，將 session 標記為可重連"""
        detached = []
        for session in self._sessions.values():
            if session.websocket_sid == websocket_sid:
                session.websocket_sid = None
                session.last_activity = datetime.now()
                detached.append(session.session_id)
        return detached

    def reattach_websocket(self, session_id: str, websocket_sid: str) -> bool:
        """重新連接 WebSocket 到現有 session"""
        session = self._sessions.get(session_id)
        if session and session.websocket_sid is None:
            session.websocket_sid = websocket_sid
            session.last_activity = datetime.now()
            return True
        return False

    def get_detached_sessions(self, user_id: Optional[int] = None) -> list[TerminalSession]:
        """取得可重連的 sessions"""
        sessions = [
            s for s in self._sessions.values()
            if s.websocket_sid is None
        ]
        if user_id is not None:
            sessions = [s for s in sessions if s.user_id == user_id]
        return sessions

    async def start_cleanup_task(self) -> None:
        """啟動清理背景任務"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """停止清理背景任務"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self) -> None:
        """定期清理超時的 sessions"""
        try:
            while True:
                await asyncio.sleep(self.CLEANUP_INTERVAL)
                await self._cleanup_expired_sessions()
        except asyncio.CancelledError:
            pass

    async def _cleanup_expired_sessions(self) -> None:
        """清理超時的斷線 sessions"""
        now = datetime.now()
        expired = []

        for session_id, session in self._sessions.items():
            # 只清理已斷線且超時的 session
            if session.websocket_sid is None:
                if now - session.last_activity > self.SESSION_TIMEOUT:
                    expired.append(session_id)

        for session_id in expired:
            self.close_session(session_id)
            print(f"Cleaned up expired terminal session: {session_id}")

    def close_all(self) -> None:
        """關閉所有 sessions"""
        for session_id in list(self._sessions.keys()):
            self.close_session(session_id)


# 全域服務實例
terminal_service = TerminalService()
