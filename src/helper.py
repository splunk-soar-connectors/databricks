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

"""Shared Databricks client, result, and checkpoint helpers."""

import uuid
from contextlib import contextmanager
from functools import wraps
from urllib.parse import urlsplit

from pydantic import PrivateAttr
from soar_sdk.action_results import ActionOutput, ActionResult
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger

from . import consts

logger = getLogger()


def get_client(asset):
    from databricks.sdk import WorkspaceClient

    try:
        host = urlsplit(asset.host)
        if host.scheme != "https" or not host.hostname:
            raise ValueError("Invalid workspace host")
    except ValueError as exc:
        raise ActionFailure("Databricks host must be a valid https:// URL") from exc
    if not (asset.token or (asset.username and asset.password)):
        raise ActionFailure(consts.MISSING_AUTHENTICATION_ERROR_MESSAGE)
    return WorkspaceClient(
        host=asset.host,
        username=asset.username,
        password=asset.password,
        token=asset.token,
    )


def serialize_alert(alert):
    """Restore non-None values omitted by databricks-sdk 0.27.1 serialization."""
    payload = alert.as_dict()
    if alert.options is not None and alert.options.value is not None:
        payload["options"]["value"] = alert.options.value
    if alert.query is not None and alert.query.options is not None:
        for index, parameter in enumerate(alert.query.options.parameters or []):
            if parameter.value is not None:
                payload["query"]["options"]["parameters"][index]["value"] = (
                    parameter.value
                )
    return payload


@contextmanager
def action_errors(prefix):
    try:
        yield
    except ActionFailure:
        raise
    except Exception as exc:
        logger.debug("Databricks operation failed", exc_info=True)
        raise ActionFailure(f"{prefix}: {exc}") from exc


def failed_action_result(params, exception, action_name, outputs):
    """Keep completed rows in an SDK failure result."""
    exception.set_action_name(action_name)
    failure = ActionResult(
        status=False,
        message=str(exception),
        param=params.model_dump(by_alias=True),
    )
    for output in outputs:
        data = output.model_dump(by_alias=True)
        if "action_status" in data:
            data["action_status"] = "failed"
        failure.add_data(data)
    return failure


def validate_uuid(value, parameter_name):
    try:
        uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{parameter_name} must be a valid UUID") from exc


def migrate_alert_state(asset):
    if "alerts" not in asset.ingest_state:
        legacy = asset.ingest_state.backend.load_state() or {}
        asset.ingest_state["alerts"] = dict(legacy.get("alerts", {}))
    return dict(asset.ingest_state.get("alerts", {}))


class PollSummary(ActionOutput):
    containers_saved: int = 0
    save_failures: int = 0
    _pending_save: bool = PrivateAttr(default=False)


def retain_poll_summary(app):
    """Attach counts to the result that SDK 7.1.2 creates without a summary."""

    def decorate(poll):
        @wraps(poll)
        def inner(params, soar=app.soar_client, *args, **kwargs):
            summary = PollSummary()
            soar.set_summary(summary)
            first_result = len(app.actions_manager.get_results())
            success = poll(params, soar, *args, **kwargs)
            if not success and summary._pending_save:
                summary.save_failures += 1
            for result in app.actions_manager.get_results()[first_result:]:
                result.set_summary(summary.model_dump())
            return success

        app.actions_manager.set_action(poll.meta.identifier, inner)
        return inner

    return decorate


class StatementSummary(ActionOutput):
    status: str


def statement_summary(soar, result, success_message):
    status = getattr(result, "status", None)
    state = getattr(
        getattr(status, "state", None), "value", getattr(status, "state", None)
    )
    if state == "SUCCEEDED":
        soar.set_summary(StatementSummary(status=success_message))
    elif state in {"PENDING", "RUNNING"}:
        message = f"Databricks statement is still {state.lower()}"
        soar.set_summary(StatementSummary(status=message))
        soar.set_message(message)
    else:
        soar.set_summary(StatementSummary(status=consts.PERFORM_QUERY_ERROR_MESSAGE))
        error = getattr(status, "error", None)
        raise ActionFailure(
            getattr(error, "message", None)
            or f"Databricks statement finished in state {state or 'unknown'}"
        )


def statement_result(params, soar, result, success_message, output_class, action_name):
    """Preserve terminal SQL failure data while retaining typed successful output."""
    try:
        statement_summary(soar, result, success_message)
    except ActionFailure as exc:
        exc.set_action_name(action_name)
        failure = ActionResult(
            status=False,
            message=str(exc),
            param=params.model_dump(by_alias=True),
        )
        failure.add_data(result.as_dict())
        failure.set_summary(
            StatementSummary(status=consts.PERFORM_QUERY_ERROR_MESSAGE).model_dump()
        )
        return failure
    return output_class.model_validate(result.as_dict())
