"""The request bodies record writes send to RushDB Cloud: the same
``{label, data, options}`` shape the JavaScript SDK sends."""

from unittest import mock

from rushdb import RushDB

RECORD_ID = "0190a7e2-0000-7000-8000-000000000001"


def sent(call):
    db = RushDB("API-KEY", base_url="http://cloud.test/api/v1")
    with mock.patch.object(db, "_make_request", return_value={"data": {}}) as request:
        call(db)
    (method, path, body, headers), _ = request.call_args
    return method, path, body


def test_update_sends_the_fields_under_data_with_the_label():
    method, path, body = sent(
        lambda db: db.records.update(
            RECORD_ID, {"expires_at": "2026-12-01T00:00:00Z"}, label="Memory"
        )
    )
    assert (method, path) == ("PATCH", f"/records/{RECORD_ID}")
    assert body == {"label": "Memory", "data": {"expires_at": "2026-12-01T00:00:00Z"}}


def test_update_without_a_label_still_sends_data():
    _, _, body = sent(lambda db: db.records.update(RECORD_ID, {"status": "done"}))
    assert body == {"data": {"status": "done"}}


def test_update_keeps_fields_named_like_body_keys_inside_data():
    data = {"label": "urgent", "options": "a,b", "data": "raw"}
    _, _, body = sent(lambda db: db.records.update(RECORD_ID, data, label="Task"))
    assert body == {"label": "Task", "data": data}


def test_update_does_not_mutate_the_callers_dict():
    data = {"status": "done"}
    sent(lambda db: db.records.update(RECORD_ID, data, label="Task"))
    assert data == {"status": "done"}


def test_set_sends_the_same_shape_over_put():
    method, path, body = sent(
        lambda db: db.records.set(RECORD_ID, {"status": "done"}, label="Task")
    )
    assert (method, path) == ("PUT", f"/records/{RECORD_ID}")
    assert body == {"data": {"status": "done"}, "label": "Task"}
