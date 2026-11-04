# Copyright (c) 2024-2026 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.
#

"""Regression coverage for conversion behavior without a live Databricks workspace."""

from inspect import unwrap
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import OnPollParams, Params

from databricks.sdk.service.workspace import ObjectType
from src.actions import create_alert
from src.actions import delete_alert
from databricks.sdk.service.jobs import RunResultState
from src.actions import execute_notebook
from src import app as hub
from src.actions import get_job_run, list_alerts, perform_query
from src.helper import PollSummary, migrate_alert_state, statement_summary


class State(dict):
    def __init__(self, legacy):
        super().__init__()
        self.backend = SimpleNamespace(load_state=lambda: legacy)


def test_legacy_checkpoints_migrate_once():
    state = State({"alerts": {"a": "2026-01-01T00:00:00Z"}})
    asset = SimpleNamespace(ingest_state=state)
    assert migrate_alert_state(asset) == {"a": "2026-01-01T00:00:00Z"}
    state["alerts"] = {"b": "new"}
    assert migrate_alert_state(asset) == {"b": "new"}


@pytest.mark.parametrize("state", ["SUCCEEDED", "PENDING", "RUNNING"])
def test_successful_and_pending_statement_states(state):
    soar = Mock()
    result = SimpleNamespace(status=SimpleNamespace(state=SimpleNamespace(value=state)))
    statement_summary(soar, result, "finished")
    assert soar.set_summary.call_args.args[0].status == (
        "finished"
        if state == "SUCCEEDED"
        else f"Databricks statement is still {state.lower()}"
    )


def test_failed_query_reports_vendor_error():
    result = SimpleNamespace(
        status=SimpleNamespace(
            state="FAILED", error=SimpleNamespace(message="SQL failed")
        )
    )
    with pytest.raises(ActionFailure, match="SQL failed"):
        statement_summary(Mock(), result, "finished")


def test_sparse_job_response_keeps_nested_and_unknown_fields(monkeypatch):
    payload = {
        "run_id": 123,
        "state": {"life_cycle_state": "RUNNING"},
        "new_api_property": {"a": 1},
    }
    client = Mock()
    client.jobs.get_run.return_value.as_dict.return_value = payload
    monkeypatch.setattr(get_job_run, "get_client", lambda asset: client)
    result = get_job_run.get_job_run.__wrapped__(
        get_job_run.GetJobRunParams(run_id=123), Mock(), Mock()
    )
    assert result.state.life_cycle_state == "RUNNING"
    assert result.action_status == "success"
    assert result.model_dump()["new_api_property"] == {"a": 1}


def test_empty_list_summary_is_preserved(monkeypatch):
    client = Mock()
    client.alerts.list.return_value = []
    monkeypatch.setattr(list_alerts, "get_client", lambda asset: client)
    soar = Mock()
    assert list_alerts.list_alerts.__wrapped__(Params(), soar, Mock()) == []
    assert soar.set_summary.call_args.args[0].model_dump(by_alias=True) == {
        "status": "Successfully listed alerts",
        "Total alerts": 0,
    }


def test_query_rows_preserve_null_cells():
    payload = {
        "statement_id": "id",
        "manifest": {"schema": {"columns": [{"name": "value"}]}},
        "result": {"data_array": [["one"], [None]]},
    }
    result = perform_query.PerformQueryOutput.model_validate(payload)
    data = result.model_dump(by_alias=True, exclude_none=True)
    assert data["result"]["data_array"] == [["one"], [None]]
    assert data["manifest"]["schema"]["columns"][0]["name"] == "value"


def test_poll_commits_checkpoint_after_container_is_consumed(monkeypatch):
    state = State({"alerts": {"old": "2026-01-01T00:00:00Z"}})
    asset = SimpleNamespace(ingest_state=state)
    alert = SimpleNamespace(
        id="new",
        name="Alert",
        last_triggered_at="2026-01-02T00:00:00Z",
        as_dict=lambda: {"id": "new", "nested": {"x": 1}},
    )
    client = Mock()
    client.alerts.list.return_value = [alert]
    monkeypatch.setattr(hub, "get_client", lambda asset: client)
    iterator = unwrap(hub.on_poll)(
        OnPollParams(), Mock(get_summary=Mock(return_value=PollSummary())), asset
    )
    container = next(iterator)
    assert "new" not in state["alerts"]
    assert container.artifacts[0]["cef"] is not container.artifacts[0]["data"]
    with pytest.raises(StopIteration):
        next(iterator)
    assert state["alerts"]["new"] == alert.last_triggered_at


def test_invalid_checkpoint_is_rejected_before_yield(monkeypatch):
    state = State({})
    asset = SimpleNamespace(ingest_state=state)
    client = Mock()
    client.alerts.list.return_value = [
        SimpleNamespace(id="bad", last_triggered_at="invalid")
    ]
    monkeypatch.setattr(hub, "get_client", lambda asset: client)
    with pytest.raises(ActionFailure):
        next(
            unwrap(hub.on_poll)(
                OnPollParams(),
                Mock(get_summary=Mock(return_value=PollSummary())),
                asset,
            )
        )
    assert state["alerts"] == {}


def test_create_alert_resolves_folder(monkeypatch):
    client = Mock()
    client.workspace.get_status.return_value = SimpleNamespace(
        object_type=ObjectType.DIRECTORY, object_id=42
    )
    client.alerts.create.return_value.as_dict.return_value = {"id": "new-alert"}
    monkeypatch.setattr(create_alert, "get_client", lambda asset: client)
    params = create_alert.CreateAlertParams(
        name="alert",
        query_id="q",
        column="count",
        operator=">",
        value="1",
        parent="/Workspace/Folder",
    )
    result = create_alert.create_alert.__wrapped__(params, Mock(), Mock())
    assert result.id == "new-alert"
    assert client.alerts.create.call_args.kwargs["parent"] == "folders/42"


def test_perform_query_converts_timeout_and_omits_unused_options(monkeypatch):
    client = Mock()
    client.statement_execution.execute_statement.return_value = SimpleNamespace(
        status=SimpleNamespace(state="PENDING"),
        as_dict=lambda: {"status": {"state": "PENDING"}},
    )
    monkeypatch.setattr(perform_query, "get_client", lambda asset: client)
    params = perform_query.PerformQueryParams(
        statement="select 1", warehouse_id="w", wait_timeout=0, schema="default"
    )
    perform_query.perform_query.__wrapped__(params, Mock(), Mock())
    kwargs = client.statement_execution.execute_statement.call_args.kwargs
    assert kwargs["wait_timeout"] == "0s"
    assert kwargs["schema"] == "default"
    assert "on_wait_timeout" not in kwargs


def test_invalid_timeout_never_calls_vendor(monkeypatch):
    client = Mock()
    monkeypatch.setattr(perform_query, "get_client", lambda asset: client)
    params = perform_query.PerformQueryParams(
        statement="select 1", warehouse_id="w", wait_timeout=2
    )
    with pytest.raises(ActionFailure, match="wait_timeout"):
        perform_query.perform_query.__wrapped__(params, Mock(), Mock())
    client.statement_execution.execute_statement.assert_not_called()


def test_delete_alert_removes_migrated_checkpoint(monkeypatch):
    alert_id = "1ad424e7-323e-4c78-875a-d1c29831160c"
    state = State({"alerts": {alert_id: "2026-01-01T00:00:00Z"}})
    client = Mock()
    monkeypatch.setattr(delete_alert, "get_client", lambda asset: client)
    delete_alert.delete_alert.__wrapped__(
        delete_alert.DeleteAlertParams(alert_id=alert_id),
        Mock(),
        SimpleNamespace(ingest_state=state),
    )
    client.alerts.delete.assert_called_once_with(alert_id)
    assert state["alerts"] == {}


def test_notebook_failure_is_an_action_failure(monkeypatch):
    client = Mock()
    client.jobs.submit.return_value.result.return_value = SimpleNamespace(
        state=SimpleNamespace(
            result_state=RunResultState.FAILED, state_message="Notebook failed"
        ),
        as_dict=lambda: {"run_id": 123, "state": {"result_state": "FAILED"}},
    )
    monkeypatch.setattr(execute_notebook, "get_client", lambda asset: client)
    params = execute_notebook.ExecuteNotebookParams(
        notebook_path="/test", existing_cluster_id="cluster"
    )
    result = execute_notebook.execute_notebook.__wrapped__(params, Mock(), Mock())
    assert result.get_status() is False
    assert "Notebook failed" in result.get_message()
    assert result.get_data()[0]["run_id"] == 123


def test_saved_alert_is_not_ingested_again(monkeypatch):
    timestamp = "2026-01-01T00:00:00Z"
    asset = SimpleNamespace(ingest_state=State({"alerts": {"a": timestamp}}))
    client = Mock()
    client.alerts.list.return_value = [
        SimpleNamespace(id="a", last_triggered_at=timestamp)
    ]
    monkeypatch.setattr(hub, "get_client", lambda asset: client)
    assert (
        list(
            unwrap(hub.on_poll)(
                OnPollParams(),
                Mock(get_summary=Mock(return_value=PollSummary())),
                asset,
            )
        )
        == []
    )
