# File: databricks_enums.py
#
# Copyright (c) 2023 Splunk Inc.
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
    CREATE_ALERT = ('POST', '/alerts')

    def __init__(self, method, path):
        self.method = method
        self.path = path

    @property
    def api_info(self):
        return {'method': self.method, 'path': self.path}