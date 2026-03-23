"""測試 api/scheduler.py 中未覆蓋的函數"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ching_tech_os.api.scheduler import (
    _parse_trigger,
    _to_response,
    _collect_static_schedules,
)


class TestParseSchedulerTrigger:
    """測試 api/scheduler._parse_trigger"""

    def test_cron(self):
        trigger = CronTrigger(hour="8", minute="30")
        t_type, config = _parse_trigger(trigger)
        assert t_type == "cron"
        assert "hour" in config

    def test_interval_hours_minutes(self):
        trigger = IntervalTrigger(hours=2, minutes=15)
        t_type, config = _parse_trigger(trigger)
        assert t_type == "interval"
        assert config["hours"] == 2
        assert config["minutes"] == 15

    def test_interval_minutes_only(self):
        trigger = IntervalTrigger(minutes=10)
        t_type, config = _parse_trigger(trigger)
        assert t_type == "interval"
        assert config["minutes"] == 10

    def test_interval_seconds_only(self):
        trigger = IntervalTrigger(seconds=45)
        t_type, config = _parse_trigger(trigger)
        assert t_type == "interval"
        assert config["seconds"] == 45

    def test_unknown_trigger(self):
        t_type, config = _parse_trigger(MagicMock())
        assert t_type == "cron"
        assert config == {}


class TestToResponse:
    def test_basic(self):
        now = datetime.now(timezone.utc)
        task = {
            "id": uuid4(),
            "name": "test",
            "description": "desc",
            "trigger_type": "cron",
            "trigger_config": {"hour": "8"},
            "executor_type": "agent",
            "executor_config": {},
            "is_enabled": True,
            "created_at": now,
            "updated_at": now,
        }
        with patch(
            "ching_tech_os.services.task_scheduler.get_dynamic_job_next_run",
            return_value=None,
        ):
            resp = _to_response(task)
            assert resp.name == "test"
            assert resp.source == "dynamic"

    def test_with_next_run(self):
        now = datetime.now(timezone.utc)
        task = {
            "id": uuid4(),
            "name": "test2",
            "description": None,
            "trigger_type": "interval",
            "trigger_config": {"minutes": 5},
            "executor_type": "skill_script",
            "executor_config": {},
            "is_enabled": True,
            "created_at": now,
            "updated_at": now,
        }
        next_run = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
        with patch(
            "ching_tech_os.services.task_scheduler.get_dynamic_job_next_run",
            return_value=next_run,
        ):
            resp = _to_response(task)
            assert resp.next_run_at == next_run


class TestCollectStaticSchedules:
    def test_with_cron_job(self):
        mock_job = MagicMock()
        mock_job.id = "proactive_push"
        mock_job.name = "主動推播"
        mock_job.trigger = CronTrigger(hour="9")
        mock_job.next_run_time = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)

        with patch(
            "ching_tech_os.services.scheduler.scheduler"
        ) as mock_sched:
            mock_sched.get_jobs.return_value = [mock_job]
            result = _collect_static_schedules()
            assert len(result) == 1
            assert result[0].source == "system"

    def test_skips_dynamic(self):
        mock_job = MagicMock()
        mock_job.id = "dynamic:xxx"

        with patch(
            "ching_tech_os.services.scheduler.scheduler"
        ) as mock_sched:
            mock_sched.get_jobs.return_value = [mock_job]
            result = _collect_static_schedules()
            assert len(result) == 0

    def test_module_source(self):
        mock_job = MagicMock()
        mock_job.id = "voice:cleanup"
        mock_job.name = "清理"
        mock_job.trigger = IntervalTrigger(hours=1)
        mock_job.next_run_time = None

        with patch(
            "ching_tech_os.services.scheduler.scheduler"
        ) as mock_sched:
            mock_sched.get_jobs.return_value = [mock_job]
            result = _collect_static_schedules()
            assert len(result) == 1
            assert result[0].source == "module"
