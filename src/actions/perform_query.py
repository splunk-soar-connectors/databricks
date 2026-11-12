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
from pydantic import ConfigDict
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import PermissiveActionOutput, ActionOutput, OutputField
from soar_sdk.params import Params, Param
from ..app import app, Asset
from .. import consts
from ..helper import get_client, statement_result


class PerformQueryParams(Params):
    model_config = ConfigDict(serialize_by_alias=True)

    statement: str = Param(description="SQL statement to execute")
    warehouse_id: str = Param(description="Warehouse upon which to execute a statement")
    wait_timeout: int | None = Param(
        description="The time in seconds the API service will wait for the statement's result. Can be set to 0 or to a value between 5 and 50. When set to 0 the statement will execute in asynchronous mode"
    )
    on_wait_timeout: str = Param(
        description="When in synchronous mode with wait_timeout > 0s the action taken when the timeout is reached",
        default="CANCEL",
        value_list=["CONTINUE", "CANCEL"],
    )
    byte_limit: int | None = Param(
        description="Applies the given byte limit to the statement's result size"
    )
    catalog: str | None = Param(
        description="Sets default catalog for statement execution, similar to USE CATALOG in SQL"
    )
    schema_name: str | None = Param(
        description="Sets default schema for statement execution, similar to USE SCHEMA in SQL.",
        alias="schema",
        required=False,
    )
    disposition: str = Param(
        description="The result disposition",
        default="INLINE",
        value_list=["INLINE", "EXTERNAL_LINKS"],
    )
    format: str = Param(
        description="The result format",
        default="JSON_ARRAY",
        value_list=["JSON_ARRAY", "ARROW_STREAM"],
    )


class ResultOutput(PermissiveActionOutput):
    row_count: int | None = OutputField(
        column_name="Rows Returned", example_values=[1000, 5]
    )
    data_array: list[list[str | None]] | None = OutputField(example_values=["10282"])
    row_offset: int | None = OutputField(example_values=[0])
    chunk_index: int | None = OutputField(example_values=[0])


class StatusOutput(PermissiveActionOutput):
    state: str | None = OutputField(
        column_name="Query State", example_values=["SUCCEEDED"]
    )


class ChunksOutput(PermissiveActionOutput):
    row_count: int | None = OutputField(example_values=[1000, 5])
    row_offset: int | None = OutputField(example_values=[0])
    chunk_index: int | None = OutputField(example_values=[0])


class ColumnsOutput(PermissiveActionOutput):
    name: str | None = OutputField(example_values=["route", "tpep_pickup_datetime"])
    position: int | None = OutputField(example_values=[0])
    type_name: str | None = OutputField(example_values=["STRING", "TIMESTAMP"])
    type_text: str | None = OutputField(example_values=["STRING", "TIMESTAMP"])


class SchemaOutput(ActionOutput):
    columns: list[ColumnsOutput] | None = None
    column_count: int | None = OutputField(example_values=[2, 6])


class ManifestOutput(PermissiveActionOutput):
    chunks: list[ChunksOutput] | None = None
    format: str | None = OutputField(example_values=["JSON_ARRAY"])
    schema_name: SchemaOutput | None = OutputField(alias="schema")
    total_row_count: int | None = OutputField(example_values=[1000, 5])
    total_chunk_count: int | None = OutputField(example_values=[1])
    truncated: bool | None = OutputField(example_values=[False])


class PerformQueryOutput(ActionOutput):
    statement_id: str | None = OutputField(
        column_name="Statement Id",
        example_values=["01edd5a1-16c6-136e-9b1e-95fc566d5199"],
    )
    status: StatusOutput | None = None
    result: ResultOutput | None = None
    manifest: ManifestOutput | None = None


class Summary(ActionOutput):
    status: str


@app.action(
    name="perform query",
    identifier="perform_query",
    description="Perform a SQL query",
    action_type="generic",
    read_only=False,
    output_class=PerformQueryOutput,
    summary_type=Summary,
    render_as="table",
)
def perform_query(params: PerformQueryParams, soar: SOARClient, asset: Asset):
    with action_errors(consts.PERFORM_QUERY_ERROR_MESSAGE):
        client = get_client(asset)
        from databricks.sdk.service.sql import (
            Disposition,
            ExecuteStatementRequestOnWaitTimeout,
            Format,
        )

        kwargs = params.model_dump(exclude_none=True, by_alias=True)
        if params.wait_timeout is not None:
            if params.wait_timeout != 0 and (not 5 <= params.wait_timeout <= 50):
                raise ValueError("wait_timeout must be 0 or between 5 and 50 seconds")
            kwargs["wait_timeout"] = f"{params.wait_timeout}s"
            if params.wait_timeout:
                kwargs["on_wait_timeout"] = ExecuteStatementRequestOnWaitTimeout(
                    params.on_wait_timeout
                )
            else:
                kwargs.pop("on_wait_timeout", None)
        else:
            kwargs.pop("on_wait_timeout", None)
        kwargs["format"] = Format(params.format)
        kwargs["disposition"] = Disposition(params.disposition)
        result = client.statement_execution.execute_statement(**kwargs)
        return statement_result(
            params,
            soar,
            result,
            consts.PERFORM_QUERY_SUCCESS_MESSAGE,
            PerformQueryOutput,
            "perform query",
        )
