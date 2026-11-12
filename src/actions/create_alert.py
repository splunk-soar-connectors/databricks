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
from soar_sdk.action_results import PermissiveActionOutput, ActionOutput, OutputField
from soar_sdk.params import Params, Param
from ..app import app, Asset
from .. import consts
from ..helper import get_client, serialize_alert


class CreateAlertParams(Params):
    name: str = Param(description="Name of channel")
    query_id: str = Param(
        description="ID of the query evaluated by the alert",
        primary=True,
        cef_types=["databricks query id"],
    )
    column: str = Param(
        description="Name of column in the query result to compare in alert evaluation"
    )
    operator: str = Param(
        description="Operator used to compare in alert evaluation",
        value_list=[">", ">=", "<", "<=", "==", "!="],
    )
    value: str = Param(description="Value used to compare in alert evaluation")
    custom_body: str | None = Param(description="Custom body of alert notification")
    custom_subject: str | None = Param(
        description="Custom subject of alert notification"
    )
    muted: bool | None = Param(
        description="Whether or not the alert is muted", default=False
    )
    rearm: int | None = Param(
        description="Number of seconds after being triggered before the alert rearms itself and can be triggered again. If not set, alert will never be triggered again"
    )
    parent: str | None = Param(
        description="The identifier of the workspace folder containing the alert. The default is the user's home folder"
    )
    empty_result_state: str | None = Param(
        description="State that alert evaluates to when query result is empty",
        value_list=["ok", "triggered", "unknown"],
    )


class UserOutput(ActionOutput):
    id: int | None = OutputField(example_values=[1392537950520258])
    name: str | None = OutputField(example_values=["Test User"])
    email: str | None = OutputField(
        cef_types=["email"], example_values=["testuser@example.com"]
    )


class MultivaluesoptionsOutput(ActionOutput):
    prefix: str | None = None
    suffix: str | None = None
    separator: str | None = OutputField(example_values=[","])


class ParametersOutput(PermissiveActionOutput):
    """Keep polymorphic parameter values without imposing a scalar type."""

    name: str | None = OutputField(example_values=["pickup_date"])
    type: str | None = OutputField(example_values=["datetime-range"])
    title: str | None = OutputField(example_values=["Data Range"])
    parentWidgetId: str | None = None
    global_: bool | None = OutputField(example_values=[False], alias="global")
    enumOptions: str | None = OutputField(example_values=["10154"])
    multiValuesOptions: MultivaluesoptionsOutput | None = None


class OptionsOutput(PermissiveActionOutput):
    """Keep alert values in their API-provided string, number, or boolean type."""

    op: str | None = OutputField(example_values=[">"])
    muted: bool | None = OutputField(example_values=[True])
    column: str | None = OutputField(example_values=["total_trips"])
    parent: str | None = OutputField(
        example_values=["folders/4082822538617174", "folders/3042705489298866"]
    )
    query_plan: str | None = OutputField(example_values=[])
    aggregation: str | None = OutputField(example_values=[])
    custom_body: str | None = OutputField(
        example_values=["This is a custom body", "custom alert body"]
    )
    custom_subject: str | None = OutputField(
        example_values=["This is a custom subject", "custom alert subject"]
    )
    display_column: str | None = None
    empty_result_state: str | None = None
    folder_node_status: str | None = OutputField(example_values=["ACTIVE"])
    folder_node_internal_name: str | None = OutputField(
        example_values=[
            "tree/2359672984925037",
            "tree/2561867671938993",
            "tree/2561867671938997",
        ]
    )


class QueryOptionsOutput(ActionOutput):
    parent: str | None = None
    parameters: list[ParametersOutput] | None = None
    run_as_role: str | None = None
    apply_auto_limit: bool | None = None
    folder_node_status: str | None = None
    folder_node_internal_name: str | None = None


class QueryOutput(ActionOutput):
    id: str | None = OutputField(
        example_values=["738f7950-c5f7-4c75-b364-47eac73439dd"], column_name="Query Id"
    )
    name: str | None = OutputField(
        example_values=["Total Trips"], column_name="Query Name"
    )
    tags: list[str] | None = OutputField(example_values=["Sample"])
    query: str | None = OutputField(
        example_values=[
            "USE CATALOG SAMPLES; SELECT count(*) as total_trips FROM `samples`.`nyctaxi`.`trips` WHERE tpep_pickup_datetime BETWEEN TIMESTAMP '{{ pickup_date.start }}' AND TIMESTAMP '{{ pickup_date.end }}' AND pickup_zip IN ({{ pickupzip }})"
        ]
    )
    parent: str | None = OutputField(example_values=["folders/3494881372287936"])
    is_safe: bool | None = OutputField(example_values=[True])
    options: QueryOptionsOutput | None = None
    user_id: int | None = OutputField(example_values=[7499675406330167])
    version: float | None = OutputField(example_values=[1])
    is_draft: bool | None = OutputField(example_values=[False])
    schedule: str | None = OutputField(example_values=[])
    created_at: str | None = OutputField(example_values=["2023-04-26T22:10:39Z"])
    updated_at: str | None = OutputField(example_values=["2023-04-26T22:10:39Z"])
    description: str | None = OutputField(example_values=[])
    is_archived: bool | None = OutputField(example_values=[False])
    run_as_role: str | None = OutputField(example_values=["viewer"])
    warehouse_id: str | None = OutputField(example_values=["exampleab98bd522"])
    data_source_id: str | None = OutputField(
        example_values=["468e81e8-b8f4-49f6-a817-3aaa221f3b88"]
    )
    run_as_service_principal_id: str | None = None


class ColumnOutput(ActionOutput):
    name: str | None = OutputField(example_values=["total_trips"])
    display: str | None = None
    aggregation: str | None = None


class AlertOutput(ActionOutput):
    column: ColumnOutput | None = None


class ThresholdOutput(ActionOutput):
    value: str | None = OutputField(example_values=["1"])


class ConditionsOutput(ActionOutput):
    op: str | None = OutputField(example_values=[">"])
    alert: AlertOutput | None = None
    threshold: ThresholdOutput | None = None
    query_plan: str | None = None
    empty_result_state: str | None = None


class SubscriptionsOutput(ActionOutput):
    user_id: int | None = OutputField(example_values=[1392537950520258])


class CreateAlertOutput(PermissiveActionOutput):
    """Preserve polymorphic alert values and query parameters."""

    id: str | None = OutputField(
        cef_types=["databricks alert id"],
        example_values=[
            "1d7a3867-8a7d-45a7-8fd5-904724167067",
            "6bb3ad87-01b7-438b-ae1b-38515d5435f6",
            "0440b52c-9deb-4de7-b7a1-bdb3e2170da6",
        ],
        column_name="Alert Id",
    )
    name: str | None = OutputField(
        example_values=["Test alert", "test playbook alert"], column_name="Alert Name"
    )
    query: QueryOutput | None = None
    created_at: str | None = OutputField(
        example_values=[
            "2023-06-24T21:54:47Z",
            "2023-06-26T02:10:12Z",
            "2023-06-26T02:36:39Z",
        ],
        column_name="Created At",
    )
    user: UserOutput | None = None
    rearm: int | None = OutputField(example_values=[5, 10])
    state: str | None = OutputField(example_values=["unknown"])
    parent: str | None = OutputField(
        example_values=["folders/4082822538617174", "folders/3042705489298866"]
    )
    options: OptionsOutput | None = None
    user_id: int | None = OutputField(example_values=[1392537950520258])
    conditions: ConditionsOutput | None = None
    updated_at: str | None = OutputField(
        example_values=[
            "2023-06-24T21:54:47Z",
            "2023-06-26T02:10:12Z",
            "2023-06-26T02:36:39Z",
        ]
    )
    is_archived: bool | None = OutputField(example_values=[False])
    warehouse_id: str | None = None
    subscriptions: list[SubscriptionsOutput] | None = None
    permission_tier: str | None = OutputField(example_values=["CAN_MANAGE"])
    last_triggered_at: str | None = None


class Summary(ActionOutput):
    status: str = OutputField(column_name="Status")


@app.action(
    name="create alert",
    identifier="create_alert",
    description="Create a new alert",
    action_type="generic",
    read_only=False,
    summary_type=Summary,
    render_as="table",
)
def create_alert(
    params: CreateAlertParams, soar: SOARClient, asset: Asset
) -> CreateAlertOutput:
    with action_errors(consts.CREATE_ALERT_ERROR_MESSAGE):
        client = get_client(asset)
        from databricks.sdk.service.sql import (
            AlertOptions,
            AlertOptionsEmptyResultState,
        )
        from databricks.sdk.service.workspace import ObjectType

        options = {
            "column": params.column,
            "op": params.operator,
            "value": params.value,
        }
        for key in ("custom_body", "custom_subject", "muted"):
            if getattr(params, key) is not None:
                options[key] = getattr(params, key)
        if params.empty_result_state is not None:
            options["empty_result_state"] = AlertOptionsEmptyResultState(
                params.empty_result_state
            )
        kwargs = {
            "name": params.name,
            "query_id": params.query_id,
            "options": AlertOptions(**options),
        }
        if params.rearm is not None:
            kwargs["rearm"] = params.rearm
        if params.parent is not None:
            if params.parent.startswith("folders/"):
                kwargs["parent"] = params.parent
            else:
                parent = client.workspace.get_status(path=params.parent)
                if parent.object_type != ObjectType.DIRECTORY:
                    raise ValueError(f"parent path is not a folder: {params.parent}")
                kwargs["parent"] = f"folders/{parent.object_id}"
        result = client.alerts.create(**kwargs)
        soar.set_summary(Summary(status=consts.CREATE_ALERT_SUCCESS_MESSAGE))
        return CreateAlertOutput.model_validate(serialize_alert(result))
