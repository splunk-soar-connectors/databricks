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
from ..helper import get_client, validate_uuid


class CancelQueryParams(Params):
    statement_id: str = Param(
        description="SQL statement id",
        primary=True,
        cef_types=["databricks statement id"],
        column_name="Statement Id",
    )


class Summary(ActionOutput):
    status: str = OutputField(column_name="Status")


@app.action(
    name="cancel query",
    identifier="cancel_query",
    description="Request that an executing SQL statement be cancelled. Callers must poll for a status of the end state",
    action_type="generic",
    read_only=False,
    summary_type=Summary,
    render_as="table",
)
def cancel_query(
    params: CancelQueryParams, soar: SOARClient, asset: Asset
) -> list[ActionOutput]:
    with action_errors(consts.CANCEL_QUERY_ERROR_MESSAGE):
        client = get_client(asset)
        validate_uuid(params.statement_id, "statement_id")
        client.statement_execution.cancel_execution(params.statement_id)
        soar.set_summary(Summary(status=consts.CANCEL_QUERY_SUCCESS_MESSAGE))
        return []
