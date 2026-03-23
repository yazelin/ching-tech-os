"""測試 mcp/scheduler_tools.py"""

import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ching_tech_os.services.mcp.scheduler_tools import (
    _check_admin,
    _collect_static_schedules,
    _format_task,
    _parse_trigger,
)


# ============================================
# _check_admin
# ============================================


class TestCheckAdmin:
    @pytest.mark.asyncio
    async def test_no_user_id(self):
        """user_id 為 None"""
        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.resolve_ctos_user_id",
            return_value=None,
        ):
            uid, err = await _check_admin(None)
            assert uid is None
            assert "需要 ctos_user_id" in err

    @pytest.mark.asyncio
    async def test_non_admin(self):
        """非管理員"""
        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.resolve_ctos_user_id",
            return_value=1,
        ):
            with patch(
                "ching_tech_os.services.user.get_user_role_and_permissions",
                new_callable=AsyncMock,
                return_value={"role": "user"},
            ):
                uid, err = await _check_admin(1)
                assert uid == 1
                assert "管理員權限" in err

    @pytest.mark.asyncio
    async def test_admin(self):
        """管理員"""
        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.resolve_ctos_user_id",
            return_value=1,
        ):
            with patch(
                "ching_tech_os.services.user.get_user_role_and_permissions",
                new_callable=AsyncMock,
                return_value={"role": "admin"},
            ):
                uid, err = await _check_admin(1)
                assert uid == 1
                assert err is None


# ============================================
# _parse_trigger
# ============================================


class TestParseTrigger:
    def test_cron_trigger(self):
        """CronTrigger 解析"""
        from apscheduler.triggers.cron import CronTrigger

        trigger = CronTrigger(hour="8", minute="30")
        trigger_type, config = _parse_trigger(trigger)
        assert trigger_type == "cron"
        assert "hour" in config
        assert "minute" in config

    def test_interval_trigger_hours(self):
        """IntervalTrigger 小時"""
        from apscheduler.triggers.interval import IntervalTrigger

        trigger = IntervalTrigger(hours=2, minutes=30)
        trigger_type, config = _parse_trigger(trigger)
        assert trigger_type == "interval"
        assert config.get("hours") == 2
        assert config.get("minutes") == 30

    def test_interval_trigger_minutes(self):
        """IntervalTrigger 分鐘"""
        from apscheduler.triggers.interval import IntervalTrigger

        trigger = IntervalTrigger(minutes=15)
        trigger_type, config = _parse_trigger(trigger)
        assert trigger_type == "interval"
        assert config.get("minutes") == 15

    def test_interval_trigger_seconds(self):
        """IntervalTrigger 秒"""
        from apscheduler.triggers.interval import IntervalTrigger

        trigger = IntervalTrigger(seconds=30)
        trigger_type, config = _parse_trigger(trigger)
        assert trigger_type == "interval"
        assert config.get("seconds") == 30

    def test_unknown_trigger(self):
        """未知 trigger 類型"""
        trigger = MagicMock()
        trigger_type, config = _parse_trigger(trigger)
        assert trigger_type == "cron"
        assert config == {}


# ============================================
# _format_task
# ============================================


class TestFormatTask:
    def test_with_last_run(self):
        """有 last_run_at"""
        now = datetime.now()
        task = {
            "id": uuid4(),
            "name": "test-task",
            "description": "描述",
            "trigger_type": "cron",
            "trigger_config": {"hour": "8"},
            "executor_type": "agent",
            "executor_config": {"prompt": "hello"},
            "is_enabled": True,
            "last_run_at": now,
            "last_run_success": True,
            "last_run_error": None,
        }
        result = _format_task(task)
        assert result["name"] == "test-task"
        assert result["last_run_at"] == now.isoformat()
        assert result["last_run_success"] is True

    def test_without_last_run(self):
        """無 last_run_at"""
        task = {
            "id": uuid4(),
            "name": "new-task",
            "trigger_type": "interval",
            "trigger_config": {"minutes": 5},
            "executor_type": "skill_script",
            "executor_config": {},
            "is_enabled": False,
        }
        result = _format_task(task)
        assert result["last_run_at"] is None
        assert result["last_run_success"] is None


# ============================================
# manage_scheduled_task
# ============================================


class TestManageScheduledTask:
    """測試 manage_scheduled_task MCP 工具"""

    @pytest.mark.asyncio
    async def test_permission_denied(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(None, "需要 ctos_user_id"),
            ):
                result = await manage_scheduled_task(action="create")
                data = json.loads(result)
                assert data["success"] is False

    @pytest.mark.asyncio
    async def test_create_missing_fields(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                result = await manage_scheduled_task(action="create", name="test")
                data = json.loads(result)
                assert data["success"] is False
                assert "create 需要" in data["error"]

    @pytest.mark.asyncio
    async def test_create_success(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        task_id = uuid4()
        mock_task = {
            "id": task_id,
            "name": "new-task",
            "description": None,
            "trigger_type": "cron",
            "trigger_config": {"hour": "8"},
            "executor_type": "agent",
            "executor_config": {"prompt": "hello"},
            "is_enabled": True,
        }

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.create_scheduled_task",
                    new_callable=AsyncMock,
                    return_value=mock_task,
                ):
                    with patch(
                        "ching_tech_os.services.task_scheduler.register_dynamic_job",
                    ) as mock_register:
                        result = await manage_scheduled_task(
                            action="create",
                            name="new-task",
                            trigger_type="cron",
                            trigger_config='{"hour": "8"}',
                            executor_type="agent",
                            executor_config='{"prompt": "hello"}',
                        )
                        data = json.loads(result)
                        assert data["success"] is True
                        mock_register.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_no_task_id(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                result = await manage_scheduled_task(action="update")
                data = json.loads(result)
                assert data["success"] is False
                assert "task_id" in data["error"]

    @pytest.mark.asyncio
    async def test_delete_success(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        tid = str(uuid4())
        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.delete_scheduled_task",
                    new_callable=AsyncMock,
                    return_value=True,
                ):
                    with patch(
                        "ching_tech_os.services.task_scheduler.unregister_dynamic_job",
                    ):
                        result = await manage_scheduled_task(
                            action="delete", task_id=tid
                        )
                        data = json.loads(result)
                        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_enable_not_found(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        tid = str(uuid4())
        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.toggle_scheduled_task",
                    new_callable=AsyncMock,
                    return_value=None,
                ):
                    result = await manage_scheduled_task(
                        action="enable", task_id=tid
                    )
                    data = json.loads(result)
                    assert data["success"] is False
                    assert "不存在" in data["error"]

    @pytest.mark.asyncio
    async def test_disable_no_task_id(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                result = await manage_scheduled_task(action="disable")
                data = json.loads(result)
                assert data["success"] is False

    @pytest.mark.asyncio
    async def test_update_success(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        tid = uuid4()
        mock_task = {
            "id": tid,
            "name": "updated-task",
            "description": "updated",
            "trigger_type": "cron",
            "trigger_config": {"hour": "9"},
            "executor_type": "agent",
            "executor_config": {"prompt": "updated"},
            "is_enabled": True,
        }

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.update_scheduled_task",
                    new_callable=AsyncMock,
                    return_value=mock_task,
                ):
                    with patch(
                        "ching_tech_os.services.task_scheduler.unregister_dynamic_job",
                    ):
                        with patch(
                            "ching_tech_os.services.task_scheduler.register_dynamic_job",
                        ):
                            result = await manage_scheduled_task(
                                action="update",
                                task_id=str(tid),
                                name="updated-task",
                                trigger_config='{"hour": "9"}',
                                executor_config='{"prompt": "updated"}',
                                is_enabled=True,
                            )
                            data = json.loads(result)
                            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        tid = str(uuid4())
        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.update_scheduled_task",
                    new_callable=AsyncMock,
                    return_value=None,
                ):
                    result = await manage_scheduled_task(
                        action="update", task_id=tid, name="x"
                    )
                    data = json.loads(result)
                    assert data["success"] is False
                    assert "不存在" in data["error"]

    @pytest.mark.asyncio
    async def test_enable_success(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        tid = uuid4()
        mock_task = {
            "id": tid,
            "name": "enabled-task",
            "trigger_type": "cron",
            "trigger_config": {},
            "executor_type": "agent",
            "executor_config": {},
            "is_enabled": True,
        }

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.toggle_scheduled_task",
                    new_callable=AsyncMock,
                    return_value=mock_task,
                ):
                    with patch(
                        "ching_tech_os.services.task_scheduler.register_dynamic_job",
                    ):
                        result = await manage_scheduled_task(
                            action="enable", task_id=str(tid)
                        )
                        data = json.loads(result)
                        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_disable_success(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        tid = uuid4()
        mock_task = {
            "id": tid,
            "name": "disabled-task",
            "trigger_type": "cron",
            "trigger_config": {},
            "executor_type": "agent",
            "executor_config": {},
            "is_enabled": False,
        }

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.toggle_scheduled_task",
                    new_callable=AsyncMock,
                    return_value=mock_task,
                ):
                    with patch(
                        "ching_tech_os.services.task_scheduler.unregister_dynamic_job",
                    ):
                        result = await manage_scheduled_task(
                            action="disable", task_id=str(tid)
                        )
                        data = json.loads(result)
                        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_no_task_id(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                result = await manage_scheduled_task(action="delete")
                data = json.loads(result)
                assert data["success"] is False
                assert "task_id" in data["error"]

    @pytest.mark.asyncio
    async def test_enable_no_task_id(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                result = await manage_scheduled_task(action="enable")
                data = json.loads(result)
                assert data["success"] is False

    @pytest.mark.asyncio
    async def test_create_disabled(self):
        """建立但 is_enabled=False 不呼叫 register"""
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        mock_task = {
            "id": uuid4(),
            "name": "disabled",
            "description": None,
            "trigger_type": "cron",
            "trigger_config": {"hour": "8"},
            "executor_type": "agent",
            "executor_config": {"prompt": "x"},
            "is_enabled": False,
        }

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.create_scheduled_task",
                    new_callable=AsyncMock,
                    return_value=mock_task,
                ):
                    with patch(
                        "ching_tech_os.services.task_scheduler.register_dynamic_job",
                    ) as mock_reg:
                        result = await manage_scheduled_task(
                            action="create",
                            name="disabled",
                            trigger_type="cron",
                            trigger_config='{"hour": "8"}',
                            executor_type="agent",
                            executor_config='{"prompt": "x"}',
                            is_enabled=False,
                        )
                        data = json.loads(result)
                        assert data["success"] is True
                        mock_reg.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsupported_action(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                result = await manage_scheduled_task(action="invalid")
                data = json.loads(result)
                assert data["success"] is False
                assert "不支援" in data["error"]

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        from ching_tech_os.services.mcp.scheduler_tools import manage_scheduled_task

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.create_scheduled_task",
                    new_callable=AsyncMock,
                    side_effect=Exception("DB error"),
                ):
                    result = await manage_scheduled_task(
                        action="create",
                        name="fail",
                        trigger_type="cron",
                        trigger_config='{"hour": "8"}',
                        executor_type="agent",
                        executor_config='{"prompt": "x"}',
                    )
                    data = json.loads(result)
                    assert data["success"] is False
                    assert "DB error" in data["error"]


# ============================================
# list_scheduled_tasks
# ============================================


class TestListScheduledTasks:
    @pytest.mark.asyncio
    async def test_permission_denied(self):
        from ching_tech_os.services.mcp.scheduler_tools import list_scheduled_tasks

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(None, "需要權限"),
            ):
                result = await list_scheduled_tasks()
                data = json.loads(result)
                assert data["success"] is False

    @pytest.mark.asyncio
    async def test_list_without_static(self):
        from ching_tech_os.services.mcp.scheduler_tools import list_scheduled_tasks

        mock_tasks = [
            {
                "id": uuid4(),
                "name": "task1",
                "trigger_type": "cron",
                "trigger_config": {},
                "executor_type": "agent",
                "executor_config": {},
                "is_enabled": True,
            }
        ]
        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.list_scheduled_tasks",
                    new_callable=AsyncMock,
                    return_value=mock_tasks,
                ):
                    result = await list_scheduled_tasks(include_static=False)
                    data = json.loads(result)
                    assert data["success"] is True
                    assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_list_with_static(self):
        from ching_tech_os.services.mcp.scheduler_tools import list_scheduled_tasks

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.list_scheduled_tasks",
                    new_callable=AsyncMock,
                    return_value=[],
                ):
                    with patch(
                        "ching_tech_os.services.mcp.scheduler_tools._collect_static_schedules",
                        return_value=[{"id": "static-1", "source": "system"}],
                    ):
                        result = await list_scheduled_tasks(include_static=True)
                        data = json.loads(result)
                        assert data["success"] is True
                        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_list_exception(self):
        from ching_tech_os.services.mcp.scheduler_tools import list_scheduled_tasks

        with patch(
            "ching_tech_os.services.mcp.scheduler_tools.ensure_db_connection",
            new_callable=AsyncMock,
        ):
            with patch(
                "ching_tech_os.services.mcp.scheduler_tools._check_admin",
                new_callable=AsyncMock,
                return_value=(1, None),
            ):
                with patch(
                    "ching_tech_os.services.task_scheduler.list_scheduled_tasks",
                    new_callable=AsyncMock,
                    side_effect=Exception("DB down"),
                ):
                    result = await list_scheduled_tasks(include_static=False)
                    data = json.loads(result)
                    assert data["success"] is False


# ============================================
# _collect_static_schedules
# ============================================


class TestCollectStaticSchedules:
    def test_with_jobs(self):
        """有靜態排程"""
        from apscheduler.triggers.cron import CronTrigger

        mock_job = MagicMock()
        mock_job.id = "proactive_push"
        mock_job.name = "主動推播"
        mock_job.trigger = CronTrigger(hour="9")
        mock_job.next_run_time = datetime(2026, 1, 1, 9, 0)

        with patch(
            "ching_tech_os.services.scheduler.scheduler"
        ) as mock_sched:
            mock_sched.get_jobs.return_value = [mock_job]
            result = _collect_static_schedules()
            assert len(result) == 1
            assert result[0]["source"] == "system"
            assert result[0]["name"] == "proactive_push"

    def test_skips_dynamic_jobs(self):
        """跳過 dynamic: 開頭的 job"""
        mock_job = MagicMock()
        mock_job.id = "dynamic:some-id"

        with patch(
            "ching_tech_os.services.scheduler.scheduler"
        ) as mock_sched:
            mock_sched.get_jobs.return_value = [mock_job]
            result = _collect_static_schedules()
            assert len(result) == 0

    def test_module_source(self):
        """含冒號的 job id 標記為 module"""
        from apscheduler.triggers.interval import IntervalTrigger

        mock_job = MagicMock()
        mock_job.id = "voice:cleanup"
        mock_job.name = "語音清理"
        mock_job.trigger = IntervalTrigger(hours=1)
        mock_job.next_run_time = None

        with patch(
            "ching_tech_os.services.scheduler.scheduler"
        ) as mock_sched:
            mock_sched.get_jobs.return_value = [mock_job]
            result = _collect_static_schedules()
            assert len(result) == 1
            assert result[0]["source"] == "module"

    def test_exception_returns_empty(self):
        """異常時回傳空列表"""
        with patch(
            "ching_tech_os.services.scheduler.scheduler"
        ) as mock_sched:
            mock_sched.get_jobs.side_effect = Exception("scheduler not running")
            result = _collect_static_schedules()
            assert result == []
