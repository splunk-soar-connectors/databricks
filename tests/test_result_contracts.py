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
from src.helper import get_client, serialize_alert
from src.actions import (
    cancel_query,
    create_alert,
    delete_alert,
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
        "manifest": {"total_byte_count": 512},
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
    assert result.get_data()[0]["manifest"]["total_byte_count"] == 512
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
    "module,params_class,values,method_path",
    [
        (
            create_alert,
            create_alert.CreateAlertParams,
            {
                "name": "alert",
                "query_id": STATEMENT_ID,
                "column": "count",
                "operator": ">",
                "value": "1",
            },
            "alerts.create",
        ),
        (
            delete_alert,
            delete_alert.DeleteAlertParams,
            {"alert_id": STATEMENT_ID},
            "alerts.delete",
        ),
        (
            cancel_query,
            cancel_query.CancelQueryParams,
            {"statement_id": STATEMENT_ID},
            "statement_execution.cancel_execution",
        ),
        (
            perform_query,
            perform_query.PerformQueryParams,
            {"statement": "select 1", "warehouse_id": "w", "schema": "default"},
            "statement_execution.execute_statement",
        ),
        (
            get_query_status,
            get_query_status.GetQueryStatusParams,
            {"statement_id": STATEMENT_ID},
            "statement_execution.get_statement",
        ),
        (
            get_job_run,
            get_job_run.GetJobRunParams,
            {"run_id": LARGE_ID},
            "jobs.get_run",
        ),
        (
            get_job_output,
            get_job_output.GetJobOutputParams,
            {"run_id": LARGE_ID},
            "jobs.get_run",
        ),
        (list_warehouses, Params, {}, "warehouses.list"),
        (
            execute_notebook,
            execute_notebook.ExecuteNotebookParams,
            {"notebook_path": "/test", "existing_cluster_id": "cluster"},
            "jobs.submit",
        ),
    ],
)
def test_vendor_failures_use_sdk_error_handling(
    module, params_class, values, method_path, monkeypatch, sdk
):
    client = Mock()
    method = client
    for name in method_path.split("."):
        method = getattr(method, name)
    method.side_effect = RuntimeError("Vendor unavailable")
    monkeypatch.setattr(module, "get_client", lambda asset: client)
    params = params_class.model_validate(values)
    function = getattr(module, module.__name__.rsplit(".", 1)[-1])
    assert function(params, soar=sdk.soar, asset=sdk.asset) is False
    result = sdk.results[0]
    assert not result.get_param()
    assert result.get_data() == []
    assert "Vendor unavailable" in result.get_message()


@pytest.mark.parametrize(
    "module,params_class,values",
    [
        (delete_alert, delete_alert.DeleteAlertParams, {"alert_id": "invalid"}),
        (cancel_query, cancel_query.CancelQueryParams, {"statement_id": "invalid"}),
        (
            get_query_status,
            get_query_status.GetQueryStatusParams,
            {"statement_id": "invalid"},
        ),
    ],
)
def test_uuid_validation_failures_use_sdk_error_handling(
    module, params_class, values, monkeypatch, sdk
):
    client = Mock()
    monkeypatch.setattr(module, "get_client", lambda asset: client)
    params = params_class.model_validate(values)
    function = getattr(module, module.__name__.rsplit(".", 1)[-1])
    assert function(params, soar=sdk.soar, asset=sdk.asset) is False
    assert not sdk.results[0].get_param()
    assert "valid UUID" in sdk.results[0].get_message()
    assert client.mock_calls == []


def test_get_job_output_keeps_completed_task_on_later_failure(monkeypatch, sdk):
    client = Mock()
    client.jobs.get_run.return_value.tasks = [
        SimpleNamespace(run_id=1),
        SimpleNamespace(run_id=2),
    ]
    client.jobs.get_run_output.side_effect = [
        SimpleNamespace(
            as_dict=lambda: {
                "metadata": {"run_id": 1},
                "notebook_output": {"result": "completed output"},
            }
        ),
        RuntimeError("Second task unavailable"),
    ]
    monkeypatch.setattr(get_job_output, "get_client", lambda asset: client)
    params = get_job_output.GetJobOutputParams(run_id=LARGE_ID)
    assert (
        get_job_output.get_job_output(params, soar=sdk.soar, asset=sdk.asset) is False
    )
    result = sdk.results[0]
    assert result.get_param() == params.model_dump(by_alias=True)
    assert len(result.get_data()) == 1
    assert result.get_data()[0]["notebook_output"]["result"] == "completed output"
    assert result.get_data()[0]["metadata"]["run_id"] == 1
    assert result.get_data()[0]["action_status"] == "failed"
    assert "Second task unavailable" in result.get_message()


def test_list_warehouses_keeps_completed_page_on_later_failure(monkeypatch, sdk):
    def pages():
        yield SimpleNamespace(as_dict=lambda: {"id": "w", "name": "Warehouse"})
        raise RuntimeError("Next page unavailable")

    client = Mock()
    client.warehouses.list.return_value = pages()
    monkeypatch.setattr(list_warehouses, "get_client", lambda asset: client)
    assert (
        list_warehouses.list_warehouses(Params(), soar=sdk.soar, asset=sdk.asset)
        is False
    )
    result = sdk.results[0]
    assert len(result.get_data()) == 1
    assert result.get_data()[0]["id"] == "w"
    assert "Next page unavailable" in result.get_message()


@pytest.mark.parametrize("action", ["delete_alert", "cancel_query"])
def test_no_payload_actions_keep_empty_data(action, monkeypatch, sdk):
    module = delete_alert if action == "delete_alert" else cancel_query
    params = (
        delete_alert.DeleteAlertParams(alert_id=STATEMENT_ID)
        if action == "delete_alert"
        else cancel_query.CancelQueryParams(statement_id=STATEMENT_ID)
    )
    sdk.asset.ingest_state = {"alerts": {STATEMENT_ID: "2026-01-01T00:00:00Z"}}
    client = Mock()
    monkeypatch.setattr(module, "get_client", lambda asset: client)
    assert getattr(module, action)(params, soar=sdk.soar, asset=sdk.asset) is True
    result = sdk.results[0]
    assert result.get_data() == []
    assert result.get_param() == params.model_dump(by_alias=True)
    assert result.get_summary() == {
        "status": consts.DELETE_ALERT_SUCCESS_MESSAGE
        if action == "delete_alert"
        else consts.CANCEL_QUERY_SUCCESS_MESSAGE
    }
    if action == "delete_alert":
        assert sdk.asset.ingest_state["alerts"] == {}


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


def test_cluster_output_preserves_documented_maps(monkeypatch, sdk):
    payload = {
        "cluster_id": "cluster",
        "custom_tags": {"cluster": "production", "team": "security"},
        "spark_conf": {"spark.master": "local[*]"},
        "spark_env_vars": {"CUSTOM_ENV": "enabled"},
        "autoscale": {"min_workers": 1, "max_workers": 4},
    }
    client = Mock()
    client.clusters.list.return_value = [ClusterDetails.from_dict(payload)]
    monkeypatch.setattr(list_clusters, "get_client", lambda asset: client)
    assert list_clusters.list_clusters(Params(), soar=sdk.soar, asset=sdk.asset) is True
    data = sdk.results[0].get_data()[0]
    for key in ("custom_tags", "spark_conf", "spark_env_vars", "autoscale"):
        for name, value in payload[key].items():
            assert data[key][name] == value
    assert data["spark_conf"] == payload["spark_conf"]
    assert "cluster" not in data


def test_warehouse_output_preserves_documented_fields(monkeypatch, sdk):
    from databricks.sdk.service.sql import EndpointInfo

    payload = {
        "id": "warehouse",
        "instance_profile_arn": "arn:aws:iam::123456789012:instance-profile/test",
        "tags": {"custom_tags": [{"key": "team", "value": "security"}]},
        "channel": {"name": "CHANNEL_NAME_CURRENT", "dbsql_version": "2024.10"},
    }
    client = Mock()
    client.warehouses.list.return_value = [EndpointInfo.from_dict(payload)]
    monkeypatch.setattr(list_warehouses, "get_client", lambda asset: client)
    assert (
        list_warehouses.list_warehouses(Params(), soar=sdk.soar, asset=sdk.asset)
        is True
    )
    data = sdk.results[0].get_data()[0]
    assert data["instance_profile_arn"] == payload["instance_profile_arn"]
    assert data["tags"] == payload["tags"]
    assert data["channel"]["dbsql_version"] == "2024.10"


def test_job_output_preserves_documented_logs_and_errors(monkeypatch, sdk):
    from databricks.sdk.service.jobs import RunOutput

    payload = {
        "metadata": {"run_id": 1},
        "logs": "Task log output",
        "logs_truncated": True,
        "error": "Task failed",
        "error_trace": "Task error details",
    }
    client = Mock()
    client.jobs.get_run.return_value.tasks = [SimpleNamespace(run_id=1)]
    client.jobs.get_run_output.return_value = RunOutput.from_dict(payload)
    monkeypatch.setattr(get_job_output, "get_client", lambda asset: client)
    assert (
        get_job_output.get_job_output(
            get_job_output.GetJobOutputParams(run_id=1), soar=sdk.soar, asset=sdk.asset
        )
        is True
    )
    data = sdk.results[0].get_data()[0]
    for key in ("logs", "logs_truncated", "error", "error_trace"):
        assert data[key] == payload[key]


@pytest.mark.parametrize("action", ["create_alert", "list_alerts"])
@pytest.mark.parametrize("value", [True, False, 0, 0.0, "", 5, 5.5, "5"])
def test_alert_outputs_preserve_documented_value_types(action, value, monkeypatch, sdk):
    warning = Mock()
    monkeypatch.setattr("soar_sdk.action_results.warning", warning)
    payload = {
        "id": STATEMENT_ID,
        "rearm": 300,
        "options": {"column": "count", "op": ">", "value": value},
        "query": {
            "tags": ["production"],
            "options": {
                "catalog": "samples",
                "schema": "default",
                "parameters": [{"name": "filter", "value": value}],
            },
        },
    }
    client = Mock()
    response = Alert.from_dict(payload)
    if action == "create_alert":
        module = create_alert
        params = create_alert.CreateAlertParams(
            name="alert", query_id=STATEMENT_ID, column="count", operator=">", value="5"
        )
        client.alerts.create.return_value = response
    else:
        module = list_alerts
        params = Params()
        client.alerts.list.return_value = [response]
    monkeypatch.setattr(module, "get_client", lambda asset: client)
    assert getattr(module, action)(params, soar=sdk.soar, asset=sdk.asset) is True
    data = sdk.results[0].get_data()[0]
    assert data["options"]["value"] == value
    assert type(data["options"]["value"]) is type(value)
    assert data["rearm"] == 300
    assert isinstance(data["rearm"], int)
    assert data["query"]["tags"] == ["production"]
    assert data["query"]["options"]["catalog"] == "samples"
    assert data["query"]["options"]["schema"] == "default"
    parameter = data["query"]["options"]["parameters"][0]
    assert parameter["value"] == value
    assert type(parameter["value"]) is type(value)
    warning.assert_not_called()


@pytest.mark.parametrize(
    "output_class", [create_alert.CreateAlertOutput, list_alerts.ListAlertsOutput]
)
@pytest.mark.parametrize(
    "value",
    [True, False, 5, 5.5, "production", {"start": "2026-01-01"}, ["a", "b"], None],
)
def test_query_parameter_values_keep_their_native_type(
    output_class, value, monkeypatch
):
    warning = Mock()
    monkeypatch.setattr("soar_sdk.action_results.warning", warning)
    payload = {
        "query": {"options": {"parameters": [{"name": "filter", "value": value}]}}
    }
    output = output_class.model_validate(payload)
    actual = output.model_dump()["query"]["options"]["parameters"][0]
    assert actual["value"] == value
    assert type(actual["value"]) is type(value)
    warning.assert_not_called()


@pytest.mark.parametrize(
    "output_class", [create_alert.CreateAlertOutput, list_alerts.ListAlertsOutput]
)
@pytest.mark.parametrize("value", [False, 0, 0.0, ""])
def test_alert_output_models_preserve_falsey_values(output_class, value, monkeypatch):
    warning = Mock()
    monkeypatch.setattr("soar_sdk.action_results.warning", warning)
    output = output_class.model_validate(
        {"options": {"column": "count", "op": "==", "value": value}}
    )
    actual = output.model_dump()["options"]["value"]
    assert actual == value
    assert type(actual) is type(value)
    warning.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "alert"},
        {"options": {"column": "count", "op": "==", "value": None}},
        {"query": {}},
        {"query": {"options": {}}},
        {"query": {"options": {"parameters": []}}},
        {"query": {"options": {"parameters": [{"name": "filter", "value": None}]}}},
    ],
)
def test_alert_serialization_keeps_absent_and_none_values_unchanged(payload):
    alert = Alert.from_dict(payload)
    assert serialize_alert(alert) == alert.as_dict()


@pytest.mark.parametrize("value", [False, 0, 0.0, ""])
def test_poll_preserves_falsey_alert_values_in_cef_and_raw_data(
    value, monkeypatch, sdk
):
    backend = Mock()
    backend.load_state.return_value = {}
    asset = SimpleNamespace(
        ingest_state=AssetState(backend, "ingest", "test-asset", encrypted=False)
    )
    monkeypatch.setattr(hub.app, "_asset", asset, raising=False)
    alert = Alert.from_dict(
        {
            "id": STATEMENT_ID,
            "name": "Alert",
            "last_triggered_at": "2026-01-02T00:00:00Z",
            "options": {"column": "count", "op": "==", "value": value},
            "query": {"options": {"parameters": [{"name": "filter", "value": value}]}},
        }
    )
    client = Mock()
    client.alerts.list.return_value = [alert]
    monkeypatch.setattr(hub, "get_client", lambda asset: client)
    save = Mock(return_value=(True, "saved", 1))
    monkeypatch.setattr(hub.app.actions_manager, "save_container", save)
    assert hub.on_poll(OnPollParams(), soar=sdk.soar, asset=asset) is True
    container = save.call_args.args[0]
    for area in ("cef", "data"):
        payload = container["artifacts"][0][area]
        assert payload["options"]["value"] == value
        assert type(payload["options"]["value"]) is type(value)
        parameter = payload["query"]["options"]["parameters"][0]
        assert parameter["value"] == value
        assert type(parameter["value"]) is type(value)


@pytest.mark.parametrize("action", ["perform_query", "get_query_status"])
def test_sql_integer_counts_keep_precision_through_sdk(action, monkeypatch, sdk):
    payload = {
        "statement_id": STATEMENT_ID,
        "status": {"state": "SUCCEEDED"},
        "result": {"row_count": LARGE_ID, "row_offset": LARGE_ID, "chunk_index": 1},
        "manifest": {
            "total_row_count": LARGE_ID,
            "total_chunk_count": 2,
            "chunks": [
                {"row_count": LARGE_ID, "row_offset": LARGE_ID, "chunk_index": 1}
            ],
            "schema": {
                "column_count": 1,
                "columns": [{"name": "value", "position": 0}],
            },
        },
    }
    response = SimpleNamespace(
        status=SimpleNamespace(state="SUCCEEDED"), as_dict=lambda: payload
    )
    client = Mock()
    client.statement_execution.execute_statement.return_value = response
    client.statement_execution.get_statement.return_value = response
    module = perform_query if action == "perform_query" else get_query_status
    params = (
        perform_query.PerformQueryParams(statement="select 1", warehouse_id="w")
        if action == "perform_query"
        else get_query_status.GetQueryStatusParams(statement_id=STATEMENT_ID)
    )
    monkeypatch.setattr(module, "get_client", lambda asset: client)
    assert getattr(module, action)(params, soar=sdk.soar, asset=sdk.asset) is True
    data = sdk.results[0].get_data()[0]
    for chunk in (data["result"], data["manifest"]["chunks"][0]):
        for name in ("row_count", "row_offset"):
            assert chunk[name] == LARGE_ID
            assert type(chunk[name]) is int
        assert type(chunk["chunk_index"]) is int
    assert data["manifest"]["total_row_count"] == LARGE_ID
    assert type(data["manifest"]["total_row_count"]) is int
    assert type(data["manifest"]["total_chunk_count"]) is int
    assert type(data["manifest"]["schema"]["column_count"]) is int
    assert type(data["manifest"]["schema"]["columns"][0]["position"]) is int


@pytest.mark.parametrize(
    "output_class",
    [
        get_job_run.GetJobRunOutput,
        get_job_output.MetadataOutput,
        execute_notebook.ExecuteNotebookOutput,
    ],
)
def test_job_timings_and_attempt_counts_are_integers(output_class):
    payload = {
        "start_time": LARGE_ID,
        "end_time": LARGE_ID + 2,
        "attempt_number": 0,
        "setup_duration": 1000,
        "execution_duration": 2000,
        "cleanup_duration": 0,
    }
    output = output_class.model_validate(dict(payload))
    for name, expected in payload.items():
        actual = getattr(output, name)
        assert actual == expected
        assert type(actual) is int


@pytest.mark.parametrize(
    "output_class,payload",
    [
        (
            list_clusters.AwsAttributesOutput,
            {
                "first_on_demand": 1,
                "spot_bid_price_percent": 100,
                "ebs_volume_count": 0,
            },
        ),
        (list_clusters.DriverOutput, {"start_timestamp": LARGE_ID}),
        (
            list_clusters.ListClustersOutput,
            {
                "start_time": LARGE_ID,
                "num_workers": 0,
                "terminated_time": LARGE_ID,
                "last_restarted_time": LARGE_ID,
                "last_state_loss_time": LARGE_ID,
                "autotermination_minutes": 120,
                "jdbc_port": 10000,
                "cluster_memory_mb": 31232,
            },
        ),
        (list_warehouses.OdbcParamsOutput, {"port": 443}),
        (
            list_warehouses.ListWarehousesOutput,
            {
                "num_clusters": 0,
                "auto_stop_mins": 120,
                "max_num_clusters": 4,
                "min_num_clusters": 1,
                "num_active_sessions": 0,
            },
        ),
    ],
)
def test_compute_counts_timestamps_and_ports_are_integers(output_class, payload):
    output = output_class.model_validate(dict(payload))
    for name, expected in payload.items():
        actual = getattr(output, name)
        assert actual == expected
        assert type(actual) is int


def test_cluster_cores_preserve_fractional_values():
    output = list_clusters.ListClustersOutput.model_validate({"cluster_cores": 7.5})
    assert output.cluster_cores == 7.5
    assert output.model_dump()["cluster_cores"] == 7.5


def test_sql_output_preserves_documented_chunk_fields():
    output = perform_query.PerformQueryOutput.model_validate(
        {
            "status": {"state": "SUCCEEDED"},
            "result": {
                "external_links": [{"external_link": "https://storage.example/result"}],
                "next_chunk_index": 1,
                "byte_count": 512,
            },
            "manifest": {
                "total_byte_count": 512,
                "chunks": [{"byte_count": 512}],
                "schema": {
                    "columns": [
                        {"name": "value", "type_precision": 10, "type_scale": 2}
                    ]
                },
            },
        }
    )
    data = output.model_dump(by_alias=True)
    assert data["result"]["external_links"][0]["external_link"].endswith("/result")
    assert data["result"]["next_chunk_index"] == 1
    assert data["result"]["byte_count"] == 512
    assert data["manifest"]["total_byte_count"] == 512
    assert data["manifest"]["chunks"][0]["byte_count"] == 512
    assert data["manifest"]["schema"]["columns"][0]["type_precision"] == 10
    assert data["manifest"]["schema"]["columns"][0]["type_scale"] == 2


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
            options=None,
            query=None,
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
