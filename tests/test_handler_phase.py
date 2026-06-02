from unittest.mock import MagicMock, patch

import app.handler_phase as handler_module


def _run(user_ids=None, mock_service=None):
    if user_ids is None:
        user_ids = set()
    if mock_service is None:
        mock_service = MagicMock()
    with patch.object(handler_module, "_distinct_user_ids", return_value=user_ids), \
         patch.object(handler_module, "_make_service", return_value=mock_service):
        handler_module.handler({}, None)
    return mock_service


def test_calls_detect_for_each_user():
    svc = _run(user_ids={"user-1", "user-2"})

    assert svc.detect_and_store.call_count == 2


def test_no_users_no_calls():
    svc = _run(user_ids=set())

    svc.detect_and_store.assert_not_called()


def test_per_user_error_does_not_abort_others():
    svc = MagicMock()
    svc.detect_and_store.side_effect = Exception("boom")

    _run(user_ids={"user-1", "user-2"}, mock_service=svc)

    assert svc.detect_and_store.call_count == 2


def test_single_user_called_with_user_id():
    svc = _run(user_ids={"user-42"})

    svc.detect_and_store.assert_called_once_with("user-42")
