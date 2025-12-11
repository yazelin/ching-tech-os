"""終端機 Socket.IO 事件處理"""

import socketio

from ..services.terminal import terminal_service


def register_events(sio: socketio.AsyncServer) -> None:
    """註冊終端機相關的 Socket.IO 事件"""

    async def output_callback(session_id: str, data: bytes) -> None:
        """PTY 輸出回呼 - 發送到客戶端"""
        session = terminal_service.get_session(session_id)
        if session and session.websocket_sid:
            try:
                await sio.emit(
                    'terminal:output',
                    {
                        'session_id': session_id,
                        'data': data.decode('utf-8', errors='replace')
                    },
                    to=session.websocket_sid
                )
            except Exception as e:
                print(f"Error sending terminal output: {e}")

    # 設定輸出回呼
    terminal_service.set_output_callback(output_callback)

    @sio.on('terminal:create')
    async def handle_create(sid: str, data: dict) -> dict:
        """建立新的終端機 session"""
        try:
            cols = data.get('cols', 80)
            rows = data.get('rows', 24)
            user_id = data.get('user_id')

            session = await terminal_service.create_session(
                websocket_sid=sid,
                user_id=user_id,
                cols=cols,
                rows=rows
            )

            return {
                'success': True,
                'session_id': session.session_id
            }
        except Exception as e:
            print(f"Error creating terminal: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    @sio.on('terminal:input')
    async def handle_input(sid: str, data: dict) -> None:
        """接收客戶端輸入"""
        session_id = data.get('session_id')
        input_data = data.get('data', '')

        if not session_id or not input_data:
            return

        session = terminal_service.get_session(session_id)
        if session and session.websocket_sid == sid:
            try:
                session.write(input_data)
            except Exception as e:
                print(f"Error writing to terminal: {e}")
                await sio.emit(
                    'terminal:error',
                    {
                        'session_id': session_id,
                        'error': str(e)
                    },
                    to=sid
                )

    @sio.on('terminal:resize')
    async def handle_resize(sid: str, data: dict) -> None:
        """調整終端機視窗大小"""
        session_id = data.get('session_id')
        cols = data.get('cols', 80)
        rows = data.get('rows', 24)

        if not session_id:
            return

        session = terminal_service.get_session(session_id)
        if session and session.websocket_sid == sid:
            try:
                session.resize(rows, cols)
            except Exception as e:
                print(f"Error resizing terminal: {e}")

    @sio.on('terminal:close')
    async def handle_close(sid: str, data: dict) -> dict:
        """關閉終端機 session"""
        session_id = data.get('session_id')

        if not session_id:
            return {'success': False, 'error': 'Missing session_id'}

        session = terminal_service.get_session(session_id)
        if session and session.websocket_sid == sid:
            success = terminal_service.close_session(session_id)
            return {'success': success}

        return {'success': False, 'error': 'Session not found or unauthorized'}

    @sio.on('terminal:list')
    async def handle_list(sid: str, data: dict) -> dict:
        """列出可重連的 sessions"""
        user_id = data.get('user_id')
        sessions = terminal_service.get_detached_sessions(user_id)

        return {
            'sessions': [
                {
                    'session_id': s.session_id,
                    'created_at': s.created_at.isoformat(),
                    'last_activity': s.last_activity.isoformat(),
                    'cwd': s.get_cwd()
                }
                for s in sessions
            ]
        }

    @sio.on('terminal:reconnect')
    async def handle_reconnect(sid: str, data: dict) -> dict:
        """重新連接到現有 session"""
        session_id = data.get('session_id')

        if not session_id:
            return {'success': False, 'error': 'Missing session_id'}

        success = terminal_service.reattach_websocket(session_id, sid)
        if success:
            session = terminal_service.get_session(session_id)
            return {
                'success': True,
                'session_id': session_id,
                'created_at': session.created_at.isoformat() if session else None
            }

        return {'success': False, 'error': 'Session not found or already connected'}

    # 處理斷線
    @sio.on('disconnect')
    async def handle_disconnect(sid: str) -> None:
        """WebSocket 斷線時保留 sessions"""
        detached = terminal_service.detach_websocket(sid)
        if detached:
            print(f"Detached terminal sessions for reconnection: {detached}")
