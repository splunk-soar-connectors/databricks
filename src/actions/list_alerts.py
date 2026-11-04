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
from soar_sdk.params import Params
from ..app import app, Asset
from .. import consts
from ..helper import get_client, serialize_alert


class UserOutput(ActionOutput):
    id: int | None = OutputField(
        example_values=[7499675406330167, 1392537950520258], column_name="User Id"
    )
    name: str | None = OutputField(
        example_values=["Test User", "John Smith"], column_name="User Name"
    )
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
    parentWidgetId: str | None = OutputField(example_values=[])
    global_: bool | None = OutputField(example_values=[False], alias="global")
    enumOptions: str | None = OutputField(example_values=["10154"])
    multiValuesOptions: MultivaluesoptionsOutput | None = None


class OptionsOutput(PermissiveActionOutput):
    """Keep alert values in their API-provided string, number, or boolean type."""

    op: str | None = OutputField(example_values=[">"])
    muted: bool | None = OutputField(example_values=[False, True])
    column: str | None = OutputField(example_values=["total_trips"])
    parent: str | None = OutputField(
        example_values=["folders/3042705489298866", "folders/4082822538617174"]
    )
    query_plan: str | None = OutputField(example_values=[])
    aggregation: str | None = OutputField(example_values=[])
    display_column: str | None = OutputField(example_values=[])
    empty_result_state: str | None = OutputField(example_values=["triggered"])
    folder_node_status: str | None = OutputField(example_values=["ACTIVE"])
    folder_node_internal_name: str | None = OutputField(
        example_values=["tree/3494881372287944", "tree/2359672984925037"]
    )
    custom_body: str | None = OutputField(example_values=["This is a custom body"])
    custom_subject: str | None = OutputField(
        example_values=["This is a custom subject"]
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
        cef_types=["databricks query id"],
        example_values=["738f7950-c5f7-4c75-b364-47eac73439dd"],
        column_name="Query Id",
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
    warehouse_id: str | None = OutputField(example_values=["4790cbabexample"])
    data_source_id: str | None = OutputField(
        example_values=["468e81e8-b8f4-49f6-a817-3aaa221f3b88"]
    )
    run_as_service_principal_id: str | None = OutputField(example_values=[])


class ColumnOutput(ActionOutput):
    name: str | None = OutputField(example_values=["total_trips"])
    display: str | None = OutputField(example_values=[])
    aggregation: str | None = OutputField(example_values=[])


class AlertOutput(ActionOutput):
    column: ColumnOutput | None = None


class ThresholdOutput(ActionOutput):
    value: str | None = OutputField(example_values=["1"])


class ConditionsOutput(ActionOutput):
    op: str | None = OutputField(example_values=[">"])
    alert: AlertOutput | None = None
    threshold: ThresholdOutput | None = None
    query_plan: str | None = OutputField(example_values=[])
    empty_result_state: str | None = OutputField(example_values=["triggered"])


class SubscriptionsOutput(ActionOutput):
    user_id: int | None = OutputField(
        example_values=[7499675406330167, 1392537950520258]
    )


class RefreshSchedulesOutput(ActionOutput):
    id: str | None = OutputField(
        example_values=[
            "2f96a108-b0f4-44d5-9354-a357ae03de41",
            "1e926f5a-02b8-4643-9643-954ed15d3d2d",
        ]
    )
    cron: str | None = OutputField(example_values=["0 */10 * * * ?", "0 */2 * * * ?"])
    job_id: str | None = OutputField(
        cef_types=["sha1"], example_values=["856bb8f97877eb2example5aaf81fe8599aa2b9"]
    )
    data_source_id: str | None = OutputField(
        example_values=[
            "468e81e8-b8f4-49f6-a817-3aaa221f3b88",
            "2ba2bc63-65a5-46f6-adc8-1ab83039e7aa",
        ]
    )


class ListAlertsOutput(PermissiveActionOutput):
    """Preserve polymorphic alert values and query parameters."""

    id: str | None = OutputField(
        cef_types=["databricks alert id"],
        example_values=[
            "1ad424e7-323e-4c78-875a-d1c29831160c",
            "1d7a3867-8a7d-45a7-8fd5-904724167067",
        ],
        column_name="Alert Id",
    )
    name: str | None = OutputField(
        example_values=["my new test alert"], column_name="Alert Name"
    )
    user: UserOutput | None = None
    query: QueryOutput | None = None
    rearm: int | None = OutputField(example_values=[5])
    state: str | None = OutputField(example_values=["unknown", "triggered"])
    options: OptionsOutput | None = None
    user_id: int | None = OutputField(
        example_values=[7499675406330167, 1392537950520258]
    )
    conditions: ConditionsOutput | None = None
    created_at: str | None = OutputField(
        example_values=["2023-04-27T00:00:52Z", "2023-06-24T21:54:47Z"]
    )
    updated_at: str | None = OutputField(
        example_values=["2023-04-27T00:00:52Z", "2023-06-26T02:10:10Z"]
    )
    warehouse_id: str | None = OutputField(example_values=["d4a60a32example"])
    subscriptions: list[SubscriptionsOutput] | None = None
    last_triggered_at: str | None = OutputField(example_values=["2023-06-26T02:10:10Z"])
    refresh_schedules: list[RefreshSchedulesOutput] | None = None


class Summary(ActionOutput):
    status: str
    total: int = OutputField(alias="Total alerts")


@app.action(
    name="list alerts",
    identifier="list_alerts",
    description="List alerts",
    action_type="generic",
    read_only=True,
    summary_type=Summary,
    render_as="table",
)
def list_alerts(
    params: Params, soar: SOARClient, asset: Asset
) -> list[ListAlertsOutput]:
    with action_errors(consts.LIST_ALERTS_ERROR_MESSAGE):
        client = get_client(asset)
        items = list(client.alerts.list())
        soar.set_summary(
            Summary(status=consts.LIST_ALERTS_SUCCESS_MESSAGE, total=len(items))
        )
        return [
            ListAlertsOutput.model_validate(serialize_alert(item)) for item in items
        ]
