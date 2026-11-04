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
from ..helper import DatabricksOutput, get_client


class GetJobRunParams(Params):
    run_id: int = Param(description="Job run id")


class NotebookTaskOutput(DatabricksOutput):
    source: str | None = OutputField(example_values=["WORKSPACE"])
    notebook_path: str | None = OutputField(
        example_values=["/Users/testuser@example.com/Notebook 1"]
    )


class TaskOutput(DatabricksOutput):
    notebook_task: NotebookTaskOutput | None = None


class StateOutput(DatabricksOutput):
    life_cycle_state: str | None = OutputField(
        example_values=["RUNNING", "TERMINATED"], column_name="Life Cycle State"
    )
    state_message: str | None = OutputField(example_values=["In run"])
    user_cancelled_or_timedout: bool | None = OutputField(example_values=[False])
    result_state: str | None = OutputField(example_values=["SUCCESS"])


class ClusterSpecOutput(DatabricksOutput):
    existing_cluster_id: str | None = OutputField(
        example_values=["0624-224055-efbqpghm"]
    )


class ClusterInstanceOutput(DatabricksOutput):
    cluster_id: str | None = OutputField(example_values=["0624-224055-efbqpghm"])
    spark_context_id: str | None = OutputField(
        example_values=["8191206118150829076", "5808117308087458174"]
    )


class GetJobRunOutput(DatabricksOutput):
    run_id: int | None = OutputField(
        example_values=[68227, 86328], column_name="Run Id"
    )
    job_id: int | None = OutputField(
        example_values=[166555938500924, 713374513094130], column_name="Job Id"
    )
    state: StateOutput | None = None
    task: TaskOutput | None = None
    format: str | None = OutputField(example_values=["SINGLE_TASK"])
    end_time: float | None = OutputField(
        example_values=[0, 1687659346388, 1687745422414]
    )
    run_name: str | None = OutputField(
        example_values=["i ran a test", "sample job from test playbook"]
    )
    run_type: str | None = OutputField(example_values=["SUBMIT_RUN"])
    start_time: float | None = OutputField(
        example_values=[1687659091160, 1687745413368]
    )
    cluster_spec: ClusterSpecOutput | None = None
    run_page_url: str | None = OutputField(
        cef_types=["url"],
        example_values=[
            "https://example.cloud.databricks.com/?o=3910739429888807#job/166555938500924/run/68227",
            "https://example.cloud.databricks.com/?o=3910739429888807#job/713374513094130/run/86328",
        ],
    )
    number_in_job: int | None = OutputField(example_values=[68227, 86328])
    attempt_number: float | None = OutputField(example_values=[0])
    setup_duration: float | None = OutputField(example_values=[236000, 0])
    cleanup_duration: float | None = OutputField(example_values=[0])
    cluster_instance: ClusterInstanceOutput | None = None
    creator_user_name: str | None = OutputField(
        cef_types=["email"], example_values=["testuser@example.com"]
    )
    execution_duration: float | None = OutputField(example_values=[0, 19000, 9000])
    action_status: str | None = OutputField(column_name="Status")


class Summary(ActionOutput):
    status: str


@app.action(
    name="get job run",
    identifier="get_job_run",
    description="Get a single job run",
    action_type="generic",
    read_only=True,
    summary_type=Summary,
    render_as="table",
)
def get_job_run(
    params: GetJobRunParams, soar: SOARClient, asset: Asset
) -> GetJobRunOutput:
    with action_errors(consts.GET_JOB_RUN_ERROR_MESSAGE):
        client = get_client(asset)
        result = client.jobs.get_run(params.run_id)
        soar.set_summary(Summary(status=consts.GET_JOB_RUN_SUCCESS_MESSAGE))
        return GetJobRunOutput.model_validate(result.as_dict())
