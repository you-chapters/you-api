from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import app.handler_narrative as handler_module

TODAY = datetime.now(timezone.utc).date()
CURRENT_WEEK = TODAY.strftime("%G-W%V")
PREV_MONTH = (TODAY.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def _run(event, user_ids=None, mock_service=None):
    if user_ids is None:
        user_ids = set()
    if mock_service is None:
        mock_service = MagicMock()
    with patch.object(handler_module, "_distinct_user_ids", return_value=user_ids), \
         patch.object(handler_module, "_make_service", return_value=mock_service):
        handler_module.handler(event, None)
    return mock_service


def test_week_event_uses_current_week():
    svc = _run({"type": "week"}, user_ids={"user-1"})

    svc.get_narrative.assert_called_once_with("user-1", period_type="week", period_key=CURRENT_WEEK)


def test_month_event_uses_previous_month():
    svc = _run({"type": "month"}, user_ids={"user-1"})

    svc.get_narrative.assert_called_once_with("user-1", period_type="month", period_key=PREV_MONTH)


def test_default_type_is_week():
    svc = _run({}, user_ids={"user-1"})

    _, kwargs = svc.get_narrative.call_args
    assert kwargs["period_type"] == "week"


def test_generates_for_each_user():
    svc = _run({"type": "week"}, user_ids={"user-1", "user-2"})

    assert svc.get_narrative.call_count == 2


def test_no_users_no_calls():
    svc = _run({"type": "week"}, user_ids=set())

    svc.get_narrative.assert_not_called()


def test_per_user_error_does_not_abort_others():
    svc = MagicMock()
    svc.get_narrative.side_effect = Exception("oops")

    _run({"type": "week"}, user_ids={"user-1", "user-2"}, mock_service=svc)

    assert svc.get_narrative.call_count == 2


def test_no_force_refresh():
    svc = _run({"type": "week"}, user_ids={"user-1"})

    _, kwargs = svc.get_narrative.call_args
    assert kwargs.get("force_refresh", False) is False
