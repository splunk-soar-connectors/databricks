# Copyright (c) 2026 Splunk Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at https://www.apache.org/licenses/LICENSE-2.0

"""Check legacy result contracts through the pinned SDK's action decorator."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from soar_sdk.asset_state import AssetState
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import OnPollParams, Params

from src import app as hub
from src import consts
from src.helper import get_client
from src.actions import (
    create_alert,
    execute_notebook,
    get_job_output,
    get_job_run,
    get_query_status,
    list_alerts,
    list_clusters,
    list_warehouses,
    perform_query,
)
from databricks.sdk.service.jobs import RunResultState
from databricks.sdk.service.compute import ClusterDetails
from databricks.sdk.service.sql import Alert

LARGE_ID = 9007199254740993
STATEMENT_ID = "1ad424e7-323e-4c78-875a-d1c29831160c"


@pytest.fixture
def sdk(monkeypatch):
    results = []
    monkeypatch.setattr(hub.app.actions_manager, "add_result", results.append)
    monkeypatch.setattr(hub.app.actions_manager, "get_results", lambda: results)
    soar = Mock()
    soar.get_summary.return_value = None
    soar.get_message.return_value = ""

    def set_summary(summary):
        soar.get_summary.return_value = summary

    def set_message(message):
        soar.get_message.return_value = message

    soar.set_summary.side_effect = set_summary
    soar.set_message.side_effect = set_message
    return SimpleNamespace(results=results, soar=soar, asset=Mock())


@pytest.mark.parametrize(
    "output_class,payload,path",
    [
        (get_job_run.GetJobRunOutput, {"run_id": LARGE_ID}, ("run_id",)),
        (get_job_run.GetJobRunOutput, {"job_id": LARGE_ID}, ("job_id",)),
        (execute_notebook.ExecuteNotebookOutput, {"run_id": LARGE_ID}, ("run_id",)),
        (execute_notebook.ExecuteNotebookOutput, {"job_id": LARGE_ID}, ("job_id",)),
        (
            get_job_output.GetJobOutputOutput,
            {"metadata": {"run_id": LARGE_ID}},
            ("metadata", "run_id"),
        ),
        (
            get_job_output.GetJobOutputOutput,
            {"metadata": {"job_id": LARGE_ID}},
            ("metadata", "job_id"),
        ),
        (get_job_run.GetJobRunOutput, {"number_in_job": LARGE_ID}, ("number_in_job",)),
        (
            execute_notebook.ExecuteNotebookOutput,
            {"number_in_job": LARGE_ID},
            ("number_in_job",),
        ),
        (
            get_job_output.MetadataOutput,
            {"number_in_job": LARGE_ID},
            ("number_in_job",),
        ),
        (create_alert.CreateAlertOutput, {"user": {"id": LARGE_ID}}, ("user", "id")),
        (create_alert.CreateAlertOutput, {"user_id": LARGE_ID}, ("user_id",)),
        (
            create_alert.CreateAlertOutput,
            {"query": {"user_id": LARGE_ID}},
            ("query", "user_id"),
        ),
        (
            create_alert.CreateAlertOutput,
            {"subscriptions": [{"user_id": LARGE_ID}]},
            ("subscriptions", 0, "user_id"),
        ),
        (list_alerts.ListAlertsOutput, {"user": {"id": LARGE_ID}}, ("user", "id")),
        (list_alerts.ListAlertsOutput, {"user_id": LARGE_ID}, ("user_id",)),
        (
            list_alerts.ListAlertsOutput,
            {"query": {"user_id": LARGE_ID}},
            ("query", "user_id"),
        ),
        (
            list_alerts.ListAlertsOutput,
            {"subscriptions": [{"user_id": LARGE_ID}]},
            ("subscriptions", 0, "user_id"),
        ),
        (
            list_warehouses.ListWarehousesOutput,
            {"creator_id": LARGE_ID},
            ("creator_id",),
        ),
        (
            list_clusters.ListClustersOutput,
            {"spark_context_id": LARGE_ID},
            ("spark_context_id",),
        ),
    ],
)
def test_integer_identifiers_keep_their_exact_value(output_class, payload, path):
    value = output_class.model_validate(payload).model_dump(by_alias=True)
    for key in path:
        value = value[key]
    assert type(value) is int
    assert value == LARGE_ID


def test_job_run_id_can_feed_a_follow_up_action(monkeypatch, sdk):
    client = Mock()
    client.jobs.get_run.return_value.as_dict.return_value = {
        "run_id": LARGE_ID,
        "job_id": LARGE_ID,
    }
    monkeypatch.setattr(get_job_run, "get_client", lambda asset: client)
    assert (
        get_job_run.get_job_run(
            get_job_run.GetJobRunParams(run_id=LARGE_ID), soar=sdk.soar, asset=sdk.asset
        )
        is True
    )
    value = sdk.results[0].get_data()[0]["run_id"]
    assert get_job_output.GetJobOutputParams(run_id=value).run_id == LARGE_ID
    client.jobs.get_run.assert_called_once_with(LARGE_ID)


def test_notebook_reports_progress_on_every_poll(monkeypatch, sdk):
    client = Mock()
    progress = Mock()
    monkeypatch.setattr(execute_notebook, "get_client", lambda asset: client)
    monkeypatch.setattr(execute_notebook.logger, "progress", progress)
    states = ["PENDING", "PENDING", "RUNNING"]

    def finish(callback):
        for index, state in enumerate(states, start=1):
            payload = {"run_id": LARGE_ID, "state": {"life_cycle_state": state}}
            callback(SimpleNamespace(as_dict=lambda payload=payload: payload))
            assert progress.call_count == index
            message, *args = progress.call_args.args
            assert str(LARGE_ID) in message % tuple(args)
            assert state in message % tuple(args)
        return SimpleNamespace(
            state=SimpleNamespace(result_state=RunResultState.SUCCESS),
            as_dict=lambda: {"run_id": LARGE_ID, "state": {"result_state": "SUCCESS"}},
        )

    client.jobs.submit.return_value.result.side_effect = finish
    assert (
        execute_notebook.execute_notebook(
            execute_notebook.ExecuteNotebookParams(
                notebook_path="/test", new_cluster='{"num_workers": 1}'
            ),
            soar=sdk.soar,
            asset=sdk.asset,
        )
        is True
    )
    data = sdk.results[0].get_data()
    assert [row["state"]["life_cycle_state"] for row in data] == states
    assert sdk.results[0].get_summary() == {
        "status": consts.EXECUTE_NOTEBOOK_SUCCESS_MESSAGE
    }


def test_notebook_callback_keeps_integer_identifiers(monkeypatch, sdk):
    payload = {
        "run_id": LARGE_ID,
        "job_id": LARGE_ID,
        "state": {"result_state": "SUCCESS"},
    }
    run = SimpleNamespace(
        state=SimpleNamespace(result_state=RunResultState.SUCCESS),
        as_dict=lambda: payload,
    )
    client = Mock()

    def finish(callback):
        callback(run)
        return run

    client.jobs.submit.return_value.result.side_effect = finish
    monkeypatch.setattr(execute_notebook, "get_client", lambda asset: client)
    assert (
        execute_notebook.execute_notebook(
            execute_notebook.ExecuteNotebookParams(
                notebook_path="/test", existing_cluster_id="cluster"
            ),
            soar=sdk.soar,
            asset=sdk.asset,
        )
        is True
    )
    assert sdk.results[0].get_data()[0]["run_id"] == LARGE_ID
    assert sdk.results[0].get_data()[0]["job_id"] == LARGE_ID


@pytest.mark.parametrize("action", ["perform_query", "get_query_status"])
@pytest.mark.parametrize(
    "state", ["SUCCEEDED", "PENDING", "RUNNING", "FAILED", "CANCELED", "CLOSED", None]
)
def test_sql_result_contract_through_sdk(action, state, monkeypatch, sdk):
    payload = {
        "statement_id": STATEMENT_ID,
        "status": {
            "state": state,
            "error": {"error_code": "BAD_REQUEST", "message": "SQL failed"},
        }
        if state
        else None,
        "vendor_extension": {"retained": True},
    }
    response = SimpleNamespace(
        status=SimpleNamespace(state=state, error=SimpleNamespace(message="SQL failed"))
        if state
        else None,
        as_dict=lambda: payload,
    )
    client = Mock()
    client.statement_execution.execute_statement.return_value = response
    client.statement_execution.get_statement.return_value = response
    if action == "perform_query":
        module = perform_query
        params = module.PerformQueryParams(
            statement="select 1", warehouse_id="w", schema="default"
        )
        success_message = consts.PERFORM_QUERY_SUCCESS_MESSAGE
    else:
        module = get_query_status
        params = module.GetQueryStatusParams(statement_id=STATEMENT_ID)
        success_message = consts.GET_QUERY_STATUS_SUCCESS_MESSAGE
    monkeypatch.setattr(module, "get_client", lambda asset: client)
    successful = state in {"SUCCEEDED", "PENDING", "RUNNING"}
    assert getattr(module, action)(params, soar=sdk.soar, asset=sdk.asset) is successful
    assert len(sdk.results) == 1
    result = sdk.results[0]
    assert result.get_status() is successful
    assert result.get_data()[0]["statement_id"] == STATEMENT_ID
    assert result.get_data()[0]["status"] == payload["status"]
    assert result.get_data()[0]["vendor_extension"] == payload["vendor_extension"]
    assert result.get_param() == params.model_dump(by_alias=True)
    if successful:
        message = (
            success_message
            if state == "SUCCEEDED"
            else f"Databricks statement is still {state.lower()}"
        )
        assert result.get_summary() == {"status": message}
    else:
        assert result.get_data() == [payload]
        assert result.get_summary() == {"status": consts.PERFORM_QUERY_ERROR_MESSAGE}
        error = (
            "SQL failed" if state else "Databricks statement finished in state unknown"
        )
        assert (
            result.get_message()
            == f"Action failure in {action.replace('_', ' ')}: {error}"
        )
    if action == "perform_query":
        assert result.get_param()["schema"] == "default"
        assert "schema_name" not in result.get_param()
        assert (
            client.statement_execution.execute_statement.call_args.kwargs["schema"]
            == "default"
        )


@pytest.mark.parametrize("action", ["perform_query", "get_query_status"])
def test_sql_vendor_exceptions_still_fail_the_action(action, monkeypatch, sdk):
    client = Mock()
    client.statement_execution.execute_statement.side_effect = RuntimeError(
        "Vendor unavailable"
    )
    client.statement_execution.get_statement.side_effect = RuntimeError(
        "Vendor unavailable"
    )
    if action == "perform_query":
        module = perform_query
        params = module.PerformQueryParams(statement="select 1", warehouse_id="w")
    else:
        module = get_query_status
        params = module.GetQueryStatusParams(statement_id=STATEMENT_ID)
    monkeypatch.setattr(module, "get_client", lambda asset: client)
    assert getattr(module, action)(params, soar=sdk.soar, asset=sdk.asset) is False
    assert "Vendor unavailable" in sdk.results[0].get_message()
    assert sdk.results[0].get_data() == []


@pytest.mark.parametrize(
    "host",
    [
        "http://workspace.example",
        "HTTP://workspace.example",
        "ftp://workspace.example",
        "workspace.example",
        "https:///",
        "https://[invalid",
    ],
)
def test_invalid_workspace_hosts_fail_before_client_creation(host, monkeypatch):
    factory = Mock()
    monkeypatch.setattr("databricks.sdk.WorkspaceClient", factory)
    asset = hub.Asset(host=host, token="test-token")
    with pytest.raises(ActionFailure, match="valid https:// URL"):
        get_client(asset)
    factory.assert_not_called()


@pytest.mark.parametrize(
    "credentials",
    [
        {"token": "test-token"},
        {
            "username": "test-user",
            "password": "test-password",  # pragma: allowlist secret
        },
    ],
)
def test_https_client_keeps_existing_authentication_modes(credentials, monkeypatch):
    factory = Mock()
    monkeypatch.setattr("databricks.sdk.WorkspaceClient", factory)
    asset = hub.Asset(host="https://workspace.example", **credentials)
    assert get_client(asset) is factory.return_value
    factory.assert_called_once_with(
        host=asset.host,
        token=asset.token,
        username=asset.username,
        password=asset.password,
    )


@pytest.mark.parametrize("value", [True, False])
@pytest.mark.parametrize("action", ["list_clusters", "list_alerts"])
def test_vendor_booleans_remain_booleans_in_sdk_results(
    action, value, monkeypatch, sdk
):
    client = Mock()
    if action == "list_clusters":
        module = list_clusters
        client.clusters.list.return_value = [
            ClusterDetails.from_dict({"enable_elastic_disk": value})
        ]
    else:
        module = list_alerts
        client.alerts.list.return_value = [
            Alert.from_dict({"query": {"is_safe": value}})
        ]
    monkeypatch.setattr(module, "get_client", lambda asset: client)
    assert getattr(module, action)(Params(), soar=sdk.soar, asset=sdk.asset) is True
    data = sdk.results[0].get_data()[0]
    actual = (
        data["enable_elastic_disk"]
        if action == "list_clusters"
        else data["query"]["is_safe"]
    )
    assert actual is value


@pytest.mark.parametrize("value", [True, False])
def test_driver_health_is_boolean(value):
    output = list_clusters.ListClustersOutput.model_validate({"driver_healthy": value})
    assert output.model_dump()["driver_healthy"] is value


@pytest.mark.parametrize("state", ["SUCCESS", "FAILED", "CANCELED", "TIMEDOUT", None])
@pytest.mark.parametrize("callback", [True, False])
def test_notebook_terminal_results_keep_run_details(state, callback, monkeypatch, sdk):
    payload = {
        "run_id": LARGE_ID,
        "run_page_url": "https://workspace.example/job/1/run/123",
        "state": {"result_state": state, "state_message": "Notebook finished"}
        if state
        else None,
    }
    run = SimpleNamespace(
        state=SimpleNamespace(
            result_state=RunResultState(state), state_message="Notebook finished"
        )
        if state
        else None,
        as_dict=lambda: payload,
    )
    client = Mock()

    def finish(**kwargs):
        if callback:
            kwargs["callback"](run)
        return run

    client.jobs.submit.return_value.result.side_effect = finish
    monkeypatch.setattr(execute_notebook, "get_client", lambda asset: client)
    params = execute_notebook.ExecuteNotebookParams(
        notebook_path="/test", existing_cluster_id="cluster"
    )
    successful = state == "SUCCESS"
    assert (
        execute_notebook.execute_notebook(params, soar=sdk.soar, asset=sdk.asset)
        is successful
    )
    result = sdk.results[0]
    assert result.get_status() is successful
    assert result.get_param() == params.model_dump(by_alias=True)
    assert len(result.get_data()) == 1
    data = result.get_data()[0]
    assert data["run_id"] == LARGE_ID
    assert data["run_page_url"] == payload["run_page_url"]
    if state is None:
        assert data["state"] is None
    else:
        assert data["state"]["result_state"] == state
    assert data["action_status"] == ("success" if successful else "failed")
    assert result.get_summary() == {
        "status": consts.EXECUTE_NOTEBOOK_SUCCESS_MESSAGE
        if successful
        else consts.EXECUTE_NOTEBOOK_ERROR_MESSAGE
    }
    if not successful:
        expected = (
            "Notebook finished"
            if state
            else "Failed to get final notebook execution status"
        )
        assert result.get_message() == f"Action failure in execute notebook: {expected}"


def test_notebook_wait_error_keeps_previous_callback_results(monkeypatch, sdk):
    payload = {"run_id": LARGE_ID, "state": {"life_cycle_state": "RUNNING"}}
    client = Mock()

    def fail_after_callback(callback):
        callback(SimpleNamespace(as_dict=lambda: payload))
        raise TimeoutError("Notebook wait expired")

    client.jobs.submit.return_value.result.side_effect = fail_after_callback
    monkeypatch.setattr(execute_notebook, "get_client", lambda asset: client)
    assert (
        execute_notebook.execute_notebook(
            execute_notebook.ExecuteNotebookParams(
                notebook_path="/test", existing_cluster_id="cluster"
            ),
            soar=sdk.soar,
            asset=sdk.asset,
        )
        is False
    )
    result = sdk.results[0]
    assert result.get_data()[0]["run_id"] == LARGE_ID
    assert result.get_data()[0]["state"]["life_cycle_state"] == "RUNNING"
    assert "Notebook wait expired" in result.get_message()
    assert result.get_summary() == {"status": consts.EXECUTE_NOTEBOOK_ERROR_MESSAGE}


def test_notebook_failure_keeps_progress_and_final_run(monkeypatch, sdk):
    progress = {"run_id": LARGE_ID, "state": {"life_cycle_state": "RUNNING"}}
    final = {
        "run_id": LARGE_ID,
        "state": {"result_state": "FAILED", "state_message": "Notebook failed"},
    }
    client = Mock()

    def finish(callback):
        callback(SimpleNamespace(as_dict=lambda: progress))
        return SimpleNamespace(
            state=SimpleNamespace(
                result_state=RunResultState.FAILED, state_message="Notebook failed"
            ),
            as_dict=lambda: final,
        )

    client.jobs.submit.return_value.result.side_effect = finish
    monkeypatch.setattr(execute_notebook, "get_client", lambda asset: client)
    assert (
        execute_notebook.execute_notebook(
            execute_notebook.ExecuteNotebookParams(
                notebook_path="/test", existing_cluster_id="cluster"
            ),
            soar=sdk.soar,
            asset=sdk.asset,
        )
        is False
    )
    data = sdk.results[0].get_data()
    assert len(data) == 2
    assert data[0]["state"]["life_cycle_state"] == "RUNNING"
    assert data[1]["state"]["result_state"] == "FAILED"
    assert all(
        row["run_id"] == LARGE_ID and row["action_status"] == "failed" for row in data
    )


@pytest.mark.parametrize("failed_save", [0, 1, 2])
def test_sdk_poll_checkpoint_commit_and_failed_save_retry(
    failed_save, monkeypatch, sdk
):
    old = "2026-01-01T00:00:00Z"
    new = "2026-01-02T00:00:00Z"
    stored = {"alerts": {"old": old}}
    backend = Mock()
    backend.load_state.side_effect = lambda: stored
    backend.save_state.side_effect = stored.update
    asset = SimpleNamespace(
        ingest_state=AssetState(backend, "ingest", "test-asset", encrypted=False)
    )
    monkeypatch.setattr(hub.app, "_asset", asset, raising=False)
    client = Mock()
    client.alerts.list.return_value = [
        SimpleNamespace(
            id=key,
            name=key,
            last_triggered_at=date,
            as_dict=lambda key=key: {"id": key},
        )
        for key, date in [("old", old), ("a", new), ("b", new)]
    ]
    monkeypatch.setattr(hub, "get_client", lambda asset: client)
    outcomes = [(True, "saved", 1), (True, "saved", 2)]
    if failed_save:
        outcomes[failed_save - 1] = (False, "Save failed", None)
    save = Mock(side_effect=outcomes)
    monkeypatch.setattr(hub.app.actions_manager, "save_container", save)
    assert hub.on_poll(OnPollParams(), soar=sdk.soar, asset=asset) is (not failed_save)
    assert asset.ingest_state.in_transaction is False
    if failed_save:
        assert "ingest" not in stored
        assert sdk.results[-1].get_status() is False
        assert sdk.results[-1].get_summary() == {
            "containers_saved": failed_save - 1,
            "save_failures": 1,
        }
        save.side_effect = [(False, "Duplicate container found", 1), (True, "saved", 2)]
        assert hub.on_poll(OnPollParams(), soar=sdk.soar, asset=asset) is True
    assert stored["ingest"]["alerts"] == {"old": old, "a": new, "b": new}
    assert sdk.results[-1].get_summary() == {"containers_saved": 2, "save_failures": 0}
    first_summary = sdk.results[-1].get_summary().copy()
    assert hub.on_poll(OnPollParams(), soar=sdk.soar, asset=asset) is True
    assert sdk.results[-1].get_summary() == {"containers_saved": 0, "save_failures": 0}
    assert sdk.results[-2].get_summary() == first_summary


def test_poll_vendor_error_does_not_count_as_a_container_save_failure(monkeypatch, sdk):
    backend = Mock()
    backend.load_state.return_value = {}
    asset = SimpleNamespace(
        ingest_state=AssetState(backend, "ingest", "test-asset", encrypted=False)
    )
    monkeypatch.setattr(hub.app, "_asset", asset, raising=False)
    client = Mock()
    client.alerts.list.side_effect = RuntimeError("Vendor unavailable")
    monkeypatch.setattr(hub, "get_client", lambda asset: client)
    save = Mock()
    monkeypatch.setattr(hub.app.actions_manager, "save_container", save)
    assert hub.on_poll(OnPollParams(), soar=sdk.soar, asset=asset) is False
    assert sdk.results[0].get_summary() == {"containers_saved": 0, "save_failures": 0}
    assert "Vendor unavailable" in sdk.results[0].get_message()
    assert asset.ingest_state.in_transaction is False
    save.assert_not_called()
