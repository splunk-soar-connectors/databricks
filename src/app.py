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

"""Databricks SDK application and alert ingestion."""

from collections.abc import Iterator
from copy import deepcopy
from datetime import UTC, datetime

from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.asset import AssetField, BaseAsset, FieldCategory
from soar_sdk.logging import getLogger
from soar_sdk.models.container import Container
from soar_sdk.params import OnPollParams

from . import consts
from .helper import (
    action_errors,
    get_client,
    migrate_alert_state,
    retain_poll_summary,
    serialize_alert,
)

logger = getLogger()


class Asset(BaseAsset):
    host: str = AssetField(
        description='Databricks Host (must begin with "https://")',
        category=FieldCategory.CONNECTIVITY,
    )
    username: str | None = AssetField(
        description="Username", required=False, category=FieldCategory.CONNECTIVITY
    )
    password: str | None = AssetField(
        description="Password",
        required=False,
        sensitive=True,
        category=FieldCategory.CONNECTIVITY,
    )
    token: str | None = AssetField(
        description="Authentication Token",
        required=False,
        sensitive=True,
        category=FieldCategory.CONNECTIVITY,
    )


app = App(
    name="Databricks",
    app_type="investigative",
    logo="logo_databricks.svg",
    logo_dark="logo_databricks_dark.svg",
    product_vendor="Databricks",
    product_name="Databricks",
    publisher="Splunk",
    appid="6dcc0a06-ceb4-4412-834e-b8576a7486a6",
    fips_compliant=True,
    encrypt_cache_state=True,
    encrypt_ingest_state=True,
    asset_cls=Asset,
)


@app.test_connectivity()
def test_connectivity(asset: Asset) -> None:
    """Verify connectivity using the configured credentials."""
    logger.progress(consts.TEST_CONNECTIVITY_PROGRESS_MESSAGE)
    with action_errors(consts.TEST_CONNECTIVITY_ERROR_MESSAGE):
        get_client(asset).dbfs.get_status(consts.TEST_CONNECTIVITY_FILE_PATH)
    logger.progress(consts.TEST_CONNECTIVITY_SUCCESS_MESSAGE)


@retain_poll_summary(app)
@app.on_poll()
def on_poll(
    params: OnPollParams, soar: SOARClient, asset: Asset
) -> Iterator[Container]:
    """Ingest alerts triggered after the saved per-alert checkpoint."""
    state = migrate_alert_state(asset)
    summary = soar.get_summary()
    with action_errors("Alert ingestion failed"):
        for alert in get_client(asset).alerts.list():
            triggered = alert.last_triggered_at
            alert_id = alert.id
            if not alert_id or not triggered:
                continue
            # Validate before yielding; a malformed checkpoint must not ingest a row.
            timestamp = datetime.strptime(triggered, consts.DATETIME_FORMAT).replace(
                tzinfo=UTC
            )
            if alert_id in state and timestamp <= datetime.strptime(
                state[alert_id], consts.DATETIME_FORMAT
            ).replace(tzinfo=UTC):
                continue
            payload = serialize_alert(alert)
            container = Container(
                name=alert.name or "Databricks Alert",
                source_data_identifier=f"{alert_id}:{triggered}",
                artifacts=[{"cef": deepcopy(payload), "data": payload}],
            )
            summary._pending_save = True
            yield container
            # The SDK saves the container before resuming this generator.
            summary._pending_save = False
            summary.containers_saved += 1
            state[alert_id] = triggered
            asset.ingest_state["alerts"] = dict(state)


from .actions import (  # noqa: F401
    cancel_query,
    create_alert,
    delete_alert,
    execute_notebook,
    get_job_output,
    get_job_run,
    get_query_status,
    list_alerts,
    list_clusters,
    list_warehouses,
    make_request,
    perform_query,
)

if __name__ == "__main__":
    app.cli()
