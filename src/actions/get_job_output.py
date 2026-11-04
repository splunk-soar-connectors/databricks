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

from ..helper import action_errors, failed_action_result
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import PermissiveActionOutput, ActionOutput, OutputField
from soar_sdk.params import Params, Param
from soar_sdk.exceptions import ActionFailure
from ..app import app, Asset
from .. import consts
from ..helper import get_client


class GetJobOutputParams(Params):
    run_id: int = Param(description="Job run id")


class NotebookTaskOutput(ActionOutput):
    source: str | None = OutputField(example_values=["WORKSPACE"])
    notebook_path: str | None = OutputField(
        example_values=["/Users/testuser@example.com/sample notebook"]
    )


class TaskOutput(ActionOutput):
    notebook_task: NotebookTaskOutput | None = None


class StateOutput(ActionOutput):
    life_cycle_state: str | None = OutputField(
        example_values=["TERMINATED"], column_name="Life Cycle State"
    )
    result_state: str | None = OutputField(example_values=["SUCCESS"])
    state_message: str | None = None
    user_cancelled_or_timedout: bool | None = OutputField(example_values=[False])


class ClusterSpecOutput(ActionOutput):
    existing_cluster_id: str | None = OutputField(
        example_values=["0624-224055-efbqpghm"]
    )


class ClusterInstanceOutput(ActionOutput):
    cluster_id: str | None = OutputField(example_values=["0624-224055-efbqpghm"])
    spark_context_id: str | None = OutputField(
        example_values=["8191206118150829076", "5808117308087458174"]
    )


class MetadataOutput(ActionOutput):
    run_id: int | None = OutputField(
        example_values=[68227, 86328], column_name="Run Id"
    )
    job_id: int | None = OutputField(
        example_values=[166555938500924, 713374513094130], column_name="Job Id"
    )
    state: StateOutput | None = None
    task: TaskOutput | None = None
    format: str | None = OutputField(example_values=["SINGLE_TASK"])
    end_time: int | None = OutputField(example_values=[1687659346388, 1687745422414])
    run_name: str | None = OutputField(
        example_values=["i ran a test", "sample job from test playbook"]
    )
    run_type: str | None = OutputField(example_values=["SUBMIT_RUN"])
    start_time: int | None = OutputField(example_values=[1687659091160, 1687745413368])
    cluster_spec: ClusterSpecOutput | None = None
    run_page_url: str | None = OutputField(
        cef_types=["url"],
        example_values=[
            "https://example.cloud.databricks.com/?o=3910739429888807#job/166555938500924/run/68227",
            "https://example.cloud.databricks.com/?o=3910739429888807#job/713374513094130/run/86328",
        ],
    )
    number_in_job: int | None = OutputField(example_values=[68227, 86328])
    attempt_number: int | None = OutputField(example_values=[0])
    setup_duration: int | None = OutputField(example_values=[236000, 0])
    cleanup_duration: int | None = OutputField(example_values=[0])
    cluster_instance: ClusterInstanceOutput | None = None
    creator_user_name: str | None = OutputField(
        cef_types=["email"], example_values=["testuser@example.com"]
    )
    execution_duration: int | None = OutputField(example_values=[19000, 9000])


class NotebookOutputOutput(ActionOutput):
    result: str | None = OutputField(
        example_values=[
            '{"a": 1, "b": 2, "c": 3, "d": "test notebook return value", "current_time": "02:15:39"}',
            '{"a": 1, "b": 2, "c": 3, "d": "test notebook return value", "current_time": "02:10:18"}',
        ]
    )
    truncated: bool | None = OutputField(example_values=[False])


class GetJobOutputOutput(PermissiveActionOutput):
    """Keep additional RunOutput fields, including errors and task logs."""

    metadata: MetadataOutput | None = None
    notebook_output: NotebookOutputOutput | None = None
    action_status: str | None = OutputField(column_name="Status")


class Summary(ActionOutput):
    status: str


@app.action(
    name="get job output",
    identifier="get_job_output",
    description="Get job run output",
    action_type="generic",
    read_only=True,
    output_class=GetJobOutputOutput,
    summary_type=Summary,
    render_as="table",
)
def get_job_output(params: GetJobOutputParams, soar: SOARClient, asset: Asset):
    results = []
    try:
        with action_errors(consts.GET_JOB_OUTPUT_ERROR_MESSAGE):
            client = get_client(asset)
            run = client.jobs.get_run(params.run_id)
            if run.tasks is None:
                raise ActionFailure("This job run contains no task runs")
            for task in run.tasks:
                if task.run_id is not None:
                    results.append(
                        GetJobOutputOutput(
                            action_status="success",
                            **client.jobs.get_run_output(task.run_id).as_dict(),
                        )
                    )
            soar.set_summary(Summary(status=consts.GET_JOB_OUTPUT_SUCCESS_MESSAGE))
            return results
    except ActionFailure as exc:
        if not results:
            raise
        return failed_action_result(params, exc, "get job output", results)
