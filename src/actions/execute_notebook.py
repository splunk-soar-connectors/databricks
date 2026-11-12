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
import json
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import (
    PermissiveActionOutput,
    ActionOutput,
    ActionResult,
    OutputField,
)
from soar_sdk.params import Params, Param
from soar_sdk.exceptions import ActionFailure
from ..app import app, Asset, logger
from .. import consts
from ..helper import get_client


class ExecuteNotebookParams(Params):
    notebook_path: str = Param(
        description="The path of the notebook to be run in the Databricks workspace or remote repository"
    )
    git_source: str | None = Param(
        description="An optional specification for a remote repository containing the notebook"
    )
    existing_cluster_id: str | None = Param(
        description="The ID of an existing cluster to use for all runs of this task (required if new_cluster is unspecified)"
    )
    new_cluster: str | None = Param(
        description="An object specifying the details of the new cluster to use for this task (required if existing_cluster_id is unspecified)"
    )
    libraries: str | None = Param(
        description="An optional list of libraries to be installed on the cluster that executes the task"
    )
    timeout_seconds: int | None = Param(
        description="An optional timeout applied to the job"
    )
    run_name: str | None = Param(
        description="An optional name for the run", default="Untitled"
    )
    idempotency_token: str | None = Param(
        description="An optional token that can be used to guarantee the idempotency of job run requests. If a run with the provided token already exists, the request does not create a new run but returns the info of the existing run instead. If a run with the provided token is deleted, an error is returned"
    )
    access_control_list: str | None = Param(
        description="An optional list of permissions to set for the run"
    )


class NotebookTaskOutput(ActionOutput):
    source: str | None = OutputField(example_values=["WORKSPACE"])
    notebook_path: str | None = OutputField(
        example_values=["/Users/testuser@example.com/Notebook 1"]
    )


class TaskOutput(ActionOutput):
    notebook_task: NotebookTaskOutput | None = None


class StateOutput(ActionOutput):
    result_state: str | None = OutputField(example_values=["SUCCESS"])
    state_message: str | None = OutputField(example_values=[""])
    life_cycle_state: str | None = OutputField(example_values=["TERMINATED"])
    user_cancelled_or_timedout: bool | None = OutputField(example_values=[False])


class ClusterSpecOutput(ActionOutput):
    existing_cluster_id: str | None = OutputField(
        example_values=["0624-224055-efbqpghm"]
    )


class ClusterInstanceOutput(ActionOutput):
    cluster_id: str | None = OutputField(example_values=["0624-224055-efbqpghn"])
    spark_context_id: str | None = OutputField(example_values=["5808117308087458174"])


class ExecuteNotebookOutput(PermissiveActionOutput):
    """Keep additional Run fields, including tasks and their configuration."""

    run_id: int | None = OutputField(example_values=[6794, 86328], column_name="Run Id")
    task: TaskOutput | None = None
    state: StateOutput | None = None
    format: str | None = OutputField(example_values=["SINGLE_TASK"])
    job_id: int | None = OutputField(example_values=[713374513094130])
    end_time: int | None = OutputField(example_values=[1687745422414])
    run_name: str | None = OutputField(
        column_name="Run Name", example_values=["sample job from test playbook"]
    )
    run_type: str | None = OutputField(example_values=["SUBMIT_RUN"])
    start_time: int | None = OutputField(example_values=[1687745413368])
    cluster_spec: ClusterSpecOutput | None = None
    run_page_url: str | None = OutputField(
        cef_types=["url"],
        example_values=[
            "https://example.cloud.databricks.com/?o=3910739429888807#job/713374513094130/run/86328"
        ],
    )
    number_in_job: int | None = OutputField(example_values=[86328])
    attempt_number: int | None = OutputField(example_values=[0])
    setup_duration: int | None = OutputField(example_values=[0])
    cleanup_duration: int | None = OutputField(example_values=[0])
    cluster_instance: ClusterInstanceOutput | None = None
    creator_user_name: str | None = OutputField(
        cef_types=["email"], example_values=["testuser@example.com"]
    )
    execution_duration: int | None = OutputField(example_values=[9000])
    action_status: str | None = OutputField(column_name="Status")


class Summary(ActionOutput):
    status: str


@app.action(
    name="execute notebook",
    identifier="execute_notebook",
    description="Execute a Databricks notebook",
    action_type="generic",
    read_only=False,
    output_class=ExecuteNotebookOutput,
    summary_type=Summary,
    render_as="table",
)
def execute_notebook(params: ExecuteNotebookParams, soar: SOARClient, asset: Asset):
    results = []
    try:
        with action_errors(consts.EXECUTE_NOTEBOOK_ERROR_MESSAGE):
            client = get_client(asset)
            from databricks.sdk.service.compute import ClusterSpec, Library
            from databricks.sdk.service.iam import AccessControlRequest
            from databricks.sdk.service.jobs import (
                GitSource,
                NotebookTask,
                RunResultState,
                SubmitTask,
            )

            if bool(params.new_cluster) == bool(params.existing_cluster_id):
                raise ValueError(
                    "Specify exactly one of new_cluster and existing_cluster_id"
                )
            task = SubmitTask(
                task_key="soar_execute_notebook_action",
                notebook_task=NotebookTask(notebook_path=params.notebook_path),
            )
            if params.new_cluster is not None:
                task.new_cluster = ClusterSpec.from_dict(json.loads(params.new_cluster))
            if params.existing_cluster_id is not None:
                task.existing_cluster_id = params.existing_cluster_id
            if params.libraries is not None:
                task.libraries = [
                    Library.from_dict(item) for item in json.loads(params.libraries)
                ]
            kwargs = {"tasks": [task]}
            if params.git_source is not None:
                kwargs["git_source"] = GitSource.from_dict(
                    json.loads(params.git_source)
                )
            if params.access_control_list is not None:
                kwargs["access_control_list"] = [
                    AccessControlRequest.from_dict(item)
                    for item in json.loads(params.access_control_list)
                ]
            for key in ("timeout_seconds", "run_name", "idempotency_token"):
                if getattr(params, key) is not None:
                    kwargs[key] = getattr(params, key)

            def report_progress(run):
                output = ExecuteNotebookOutput(action_status="success", **run.as_dict())
                results.append(output)
                logger.progress(
                    "Notebook run %s: %s",
                    output.run_id,
                    output.state.life_cycle_state if output.state else "unknown",
                )

            result = client.jobs.submit(**kwargs).result(callback=report_progress)
            final_output = ExecuteNotebookOutput(
                action_status="success", **result.as_dict()
            )
            if (
                result.state is None
                or result.state.result_state != RunResultState.SUCCESS
            ) and (not results or results[-1] != final_output):
                results.append(final_output)
            if result.state is None:
                raise ActionFailure("Failed to get final notebook execution status")
            if result.state.result_state != RunResultState.SUCCESS:
                raise ActionFailure(
                    result.state.state_message
                    or f"Notebook execution finished in state {getattr(result.state.result_state, 'value', 'unknown')}"
                )
            soar.set_summary(Summary(status=consts.EXECUTE_NOTEBOOK_SUCCESS_MESSAGE))
            return results or [final_output]
    except ActionFailure as exc:
        if not results:
            raise
        exc.set_action_name("execute notebook")
        failure = ActionResult(
            status=False,
            message=str(exc),
            param=params.model_dump(by_alias=True),
        )
        for output in results:
            data = output.model_dump(by_alias=True)
            data["action_status"] = "failed"
            failure.add_data(data)
        failure.set_summary(
            Summary(status=consts.EXECUTE_NOTEBOOK_ERROR_MESSAGE).model_dump()
        )
        return failure
