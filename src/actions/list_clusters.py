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


class ClusterOutput(DatabricksOutput):
    profile: str | None = OutputField(example_values=["singleNode"])


class DatabricksOutput(DatabricksOutput):
    cluster: ClusterOutput | None = None


class SparkOutput(DatabricksOutput):
    master: str | None = OutputField(example_values=["local[*, 4]"])
    databricks: DatabricksOutput | None = None


class SparkConfOutput(DatabricksOutput):
    spark: SparkOutput | None = None


class CustomTagsOutput(DatabricksOutput):
    ResourceClass: str | None = OutputField(example_values=["SingleNode"])


class DefaultTagsOutput(DatabricksOutput):
    Vendor: str | None = OutputField(example_values=["Databricks"])
    Creator: str | None = OutputField(
        cef_types=["email"], example_values=["testuser@example.com"]
    )
    ClusterId: str | None = OutputField(
        example_values=["0424-172834-62g8ca99", "0624-224055-efbqpg99"]
    )
    ClusterName: str | None = OutputField(
        example_values=["Test User's Personal Compute Cluster", "John Smith's Cluster"]
    )


class AwsAttributesOutput(DatabricksOutput):
    zone_id: str | None = OutputField(example_values=["auto"])
    availability: str | None = OutputField(
        example_values=["ON_DEMAND", "SPOT_WITH_FALLBACK"]
    )
    first_on_demand: float | None = OutputField(example_values=[0, 1])
    spot_bid_price_percent: float | None = OutputField(example_values=[100])
    ebs_volume_count: float | None = OutputField(example_values=[0])


class InstanceSourceOutput(DatabricksOutput):
    node_type_id: str | None = OutputField(example_values=["i3.xlarge"])


class ParametersOutput(DatabricksOutput):
    inactivity_duration_min: str | None = OutputField(example_values=["4320"])


class TerminationReasonOutput(DatabricksOutput):
    code: str | None = OutputField(example_values=["INACTIVITY"])
    type: str | None = OutputField(example_values=["SUCCESS"])
    parameters: ParametersOutput | None = None


class DriverInstanceSourceOutput(DatabricksOutput):
    node_type_id: str | None = OutputField(example_values=["i3.xlarge"])


class NodeAttributesOutput(DatabricksOutput):
    is_spot: bool | None = OutputField(example_values=[False])


class NodeAwsAttributesOutput(DatabricksOutput):
    is_spot: bool | None = OutputField(example_values=[False])


class DriverOutput(DatabricksOutput):
    node_id: str | None = OutputField(
        cef_types=["md5"], example_values=["081ac1a81449example9383abef5514"]
    )
    private_ip: str | None = OutputField(
        cef_types=["ip"], example_values=["10.26.193.115"]
    )
    instance_id: str | None = OutputField(example_values=["i-0ab7bd9b85477a279"])
    host_private_ip: str | None = OutputField(
        cef_types=["ip"], example_values=["10.26.208.44"]
    )
    node_attributes: NodeAttributesOutput | None = None
    start_timestamp: float | None = OutputField(example_values=[1687733773425])
    node_aws_attributes: NodeAwsAttributesOutput | None = None


class DiskSpecOutput(DatabricksOutput):
    disk_count: float | None = OutputField(example_values=[0])


class SparkEnvVarsOutput(DatabricksOutput):
    PYSPARK_PYTHON: str | None = OutputField(
        example_values=["/databricks/python3/bin/python3"]
    )


class ListClustersOutput(DatabricksOutput):
    cluster_id: str | None = OutputField(
        cef_types=["databricks cluster id"],
        example_values=["0424-172834-62g8ca99", "0624-224055-efbqpg99"],
        column_name="Cluster Id",
    )
    cluster_name: str | None = OutputField(
        example_values=["Test User's Personal Compute Cluster", "Test User's Cluster"],
        column_name="Cluster Name",
    )
    state: str | None = OutputField(
        example_values=["TERMINATED", "RUNNING"], column_name="State"
    )
    state_message: str | None = OutputField(
        example_values=["Inactive cluster terminated (inactive for 4320 minutes).", ""],
        column_name="State Message",
    )
    policy_id: str | None = None
    spark_conf: SparkConfOutput | None = None
    start_time: float | None = OutputField(
        example_values=[1682357315089, 1687646455924]
    )
    custom_tags: CustomTagsOutput | None = None
    num_workers: float | None = OutputField(example_values=[0])
    default_tags: DefaultTagsOutput | None = None
    node_type_id: str | None = OutputField(example_values=["i3.xlarge"])
    spark_version: str | None = OutputField(
        example_values=["13.0.x-cpu-ml-scala2.12", "12.2.x-scala2.12"]
    )
    aws_attributes: AwsAttributesOutput | None = None
    cluster_source: str | None = OutputField(example_values=["UI"])
    driver_healthy: bool | None = OutputField(example_values=[True])
    runtime_engine: str | None = OutputField(example_values=["STANDARD", "PHOTON"])
    instance_source: InstanceSourceOutput | None = None
    terminated_time: float | None = OutputField(example_values=[1685993057468])
    single_user_name: str | None = OutputField(
        cef_types=["email"], example_values=["testuser@example.com"]
    )
    spark_context_id: int | None = OutputField(
        example_values=[4218622610576032053, 5808117308087458174]
    )
    creator_user_name: str | None = OutputField(
        cef_types=["email"], example_values=["testuser@example.com"]
    )
    data_security_mode: str | None = OutputField(
        example_values=["LEGACY_SINGLE_USER_STANDARD"]
    )
    last_activity_time: float | None = OutputField(
        example_values=[1685733831059, 1687745241253]
    )
    termination_reason: TerminationReasonOutput | None = None
    driver_node_type_id: str | None = OutputField(example_values=["i3.xlarge"])
    enable_elastic_disk: bool | None = OutputField(example_values=[True])
    last_restarted_time: float | None = OutputField(
        example_values=[1685721657951, 1687733852263]
    )
    last_state_loss_time: float | None = OutputField(
        example_values=[1685721657913, 1687733852234]
    )
    driver_instance_source: DriverInstanceSourceOutput | None = None
    init_scripts_safe_mode: bool | None = OutputField(example_values=[False])
    autotermination_minutes: float | None = OutputField(example_values=[4320, 120])
    effective_spark_version: str | None = OutputField(
        example_values=["13.0.x-cpu-ml-scala2.12", "12.2.x-photon-scala2.12"]
    )
    enable_local_disk_encryption: bool | None = OutputField(example_values=[False])
    driver: DriverOutput | None = None
    disk_spec: DiskSpecOutput | None = None
    jdbc_port: float | None = OutputField(example_values=[10000])
    cluster_cores: float | None = OutputField(example_values=[4])
    spark_env_vars: SparkEnvVarsOutput | None = None
    cluster_memory_mb: float | None = OutputField(example_values=[31232])


class Summary(ActionOutput):
    status: str
    total: int = OutputField(alias="Total Clusters")


@app.action(
    name="list clusters",
    identifier="list_clusters",
    description="List clusters",
    action_type="generic",
    read_only=True,
    summary_type=Summary,
    render_as="table",
)
def list_clusters(
    params: Params, soar: SOARClient, asset: Asset
) -> list[ListClustersOutput]:
    with action_errors(consts.LIST_CLUSTERS_ERROR_MESSAGE):
        client = get_client(asset)
        items = list(client.clusters.list())
        soar.set_summary(
            Summary(status=consts.LIST_CLUSTERS_SUCCESS_MESSAGE, total=len(items))
        )
        return [ListClustersOutput.model_validate(item.as_dict()) for item in items]
