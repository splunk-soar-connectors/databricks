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
from soar_sdk.action_results import ActionOutput
from soar_sdk.params import Params, Param
from ..app import app, Asset
from .. import consts
from ..helper import get_client, validate_uuid, statement_result


class GetQueryStatusParams(Params):
    statement_id: str = Param(
        description="SQL statement id",
        primary=True,
        cef_types=["databricks statement id"],
    )


from .perform_query import PerformQueryOutput as GetQueryStatusOutput


class Summary(ActionOutput):
    status: str


@app.action(
    name="get query status",
    identifier="get_query_status",
    description="Get status, manifest, and result first chunk of a SQL query",
    action_type="generic",
    read_only=True,
    output_class=GetQueryStatusOutput,
    summary_type=Summary,
    render_as="table",
)
def get_query_status(params: GetQueryStatusParams, soar: SOARClient, asset: Asset):
    with action_errors(consts.GET_QUERY_STATUS_ERROR_MESSAGE):
        client = get_client(asset)
        validate_uuid(params.statement_id, "statement_id")
        result = client.statement_execution.get_statement(params.statement_id)
        return statement_result(
            params,
            soar,
            result,
            consts.GET_QUERY_STATUS_SUCCESS_MESSAGE,
            GetQueryStatusOutput,
            "get query status",
        )
