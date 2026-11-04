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

from ..helper import action_errors
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.params import Params, Param
from ..app import app, Asset
from .. import consts
from ..helper import get_client, validate_uuid, migrate_alert_state


class DeleteAlertParams(Params):
    alert_id: str = Param(
        description="ID of the alert to delete",
        primary=True,
        cef_types=["databricks alert id"],
        column_name="Alert Id",
    )


class Summary(ActionOutput):
    status: str = OutputField(column_name="Status")


@app.action(
    name="delete alert",
    identifier="delete_alert",
    description="Delete an alert",
    action_type="investigate",
    read_only=False,
    summary_type=Summary,
    render_as="table",
)
def delete_alert(
    params: DeleteAlertParams, soar: SOARClient, asset: Asset
) -> ActionOutput:
    with action_errors(consts.DELETE_ALERT_ERROR_MESSAGE):
        client = get_client(asset)
        validate_uuid(params.alert_id, "alert_id")
        client.alerts.delete(params.alert_id)
        state = migrate_alert_state(asset)
        state.pop(params.alert_id, None)
        asset.ingest_state["alerts"] = state
        soar.set_summary(Summary(status=consts.DELETE_ALERT_SUCCESS_MESSAGE))
        return ActionOutput()
