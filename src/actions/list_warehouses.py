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
from soar_sdk.params import Params
from ..app import app, Asset
from .. import consts
from ..helper import DatabricksOutput, get_client


class HealthOutput(DatabricksOutput):
    status: str | None = OutputField(example_values=["HEALTHY"], column_name="Status")


class OdbcParamsOutput(DatabricksOutput):
    path: str | None = OutputField(
        example_values=[
            "/sql/1.0/warehouses/4790cb1ab98bd522",
            "/sql/1.0/warehouses/d4a60a3223b685ff",
        ]
    )
    port: float | None = OutputField(example_values=[443])
    hostname: str | None = OutputField(
        cef_types=["host name"],
        example_values=["example.cloud.databricks.com", "example.cloud.databricks.com"],
    )
    protocol: str | None = OutputField(cef_types=["url"], example_values=["https"])


class ChannelOutput(DatabricksOutput):
    name: str | None = OutputField(example_values=["CHANNEL_NAME_CURRENT"])


class ListWarehousesOutput(DatabricksOutput):
    id: str | None = OutputField(
        cef_types=["databricks warehouse id"],
        example_values=["d4a60a32example"],
        column_name="Warehouse Id",
    )
    name: str | None = OutputField(
        example_values=["Starter Warehouse", "HE SQL WHS"], column_name="Warehouse Name"
    )
    size: str | None = OutputField(
        example_values=["SMALL", "XXSMALL"], column_name="Size"
    )
    state: str | None = OutputField(example_values=["RUNNING"], column_name="State")
    health: HealthOutput | None = None
    jdbc_url: str | None = OutputField(
        example_values=[
            "jdbc:spark://example.cloud.databricks.com:443/default;transportMode=http;ssl=1;AuthMech=3;httpPath=/sql/1.0/warehouses/4790cb1ab98bd522;",
            "jdbc:spark://example.cloud.databricks.com:443/default;transportMode=http;ssl=1;AuthMech=3;httpPath=/sql/1.0/warehouses/d4a60a3223b685ff;",
        ]
    )
    creator_id: int | None = OutputField(
        example_values=[7499675406330167, 1392537950520258]
    )
    auto_resume: bool | None = OutputField(example_values=[True])
    odbc_params: OdbcParamsOutput | None = None
    cluster_size: str | None = OutputField(example_values=["Small", "2X-Small"])
    creator_name: str | None = OutputField(
        cef_types=["email"], example_values=["testuser@example.com"]
    )
    num_clusters: float | None = OutputField(example_values=[1])
    enable_photon: bool | None = OutputField(example_values=[True])
    auto_stop_mins: float | None = OutputField(example_values=[60, 10])
    warehouse_type: str | None = OutputField(example_values=["PRO"])
    max_num_clusters: float | None = OutputField(example_values=[1])
    min_num_clusters: float | None = OutputField(example_values=[1])
    num_active_sessions: float | None = OutputField(example_values=[0])
    spot_instance_policy: str | None = OutputField(example_values=["COST_OPTIMIZED"])
    enable_serverless_compute: bool | None = OutputField(example_values=[False])
    channel: ChannelOutput | None = None


class Summary(ActionOutput):
    status: str
    total: int = OutputField(alias="total warehouses")


@app.action(
    name="list warehouses",
    identifier="list_warehouses",
    description="List all SQL warehouses for which a user has manager permissions",
    action_type="generic",
    read_only=True,
    summary_type=Summary,
    render_as="table",
)
def list_warehouses(
    params: Params, soar: SOARClient, asset: Asset
) -> list[ListWarehousesOutput]:
    with action_errors(consts.LIST_WAREHOUSES_ERROR_MESSAGE):
        client = get_client(asset)
        items = list(client.warehouses.list())
        soar.set_summary(
            Summary(status=consts.LIST_WAREHOUSES_SUCCESS_MESSAGE, total=len(items))
        )
        return [ListWarehousesOutput.model_validate(item.as_dict()) for item in items]
