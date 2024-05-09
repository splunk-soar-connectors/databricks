# File: databricks_enums.py
#
# Copyright (c) 2024 Splunk Inc.
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

from enum import Enum


class DatabricksEndpoint(Enum):
    LIST_ALERTS = ("GET", "/preview/sql/alerts")
    LIST_CLUSTERS = ("GET", "/clusters/list")
    CREATE_ALERT = ("POST", "/preview/sql/alerts")
    DELETE_ALERT = ("DELETE", "/preview/sql/alerts/{alert_id}")
    PERFORM_QUERY = ("POST", "/sql/statements")
    LIST_WAREHOUSES = ("GET", "/sql/warehouses")
    JOB_RUN = ("GET", "/jobs/runs/get")
    JOB_RUN_OUTPUT = ("GET", "/jobs/runs/get-output")
    GET_QUERY_STATUS = ("GET", "/sql/statements/{statement_id}")
    CANCEL_QUERY = ("POST", "/sql/statements/{statement_id}/cancel")

    def __init__(self, method, path):
        self.method = method
        self.path = path

    @property
    def api_info(self):
        return {"method": self.method, "path": self.path}

    def api_info_with_interpolation(self, **values):
        """Return API info with the path interpolated using the specified values."""
        return {"method": self.method, "path": self.path.format(**values)}
