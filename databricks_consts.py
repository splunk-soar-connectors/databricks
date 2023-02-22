# File: databricks_consts.py
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

MISSING_AUTHENTICATION_ERROR_MESSAGE = \
    'Either username/password or an authentication token must be specified in the app configuration'

TEST_CONNECTIVITY_SUCCESS_MESSAGE = 'Test connectivity passed'
TEST_CONNECTIVITY_ERROR_MESSAGE = 'Test connectivity failed'
TEST_CONNECTIVITY_PROGRESS_MESSAGE = "Connecting to Databricks host"

CREATE_ALERT_SUCCESS_MESSAGE = 'Successfully created alert'
DELETE_ALERT_SUCCESS_MESSAGE = 'Successfully deleted alert'

DATABRICKS_ERROR_CODE_UNAVAILABLE = 'Unavailable'
DATABRICKS_ERROR_MESSAGE_UNAVAILABLE = 'Unavailable. Please check the asset configuration and|or the action parameters.'

UNHANDLED_ACTION_ID_ERROR_MESSAGE = 'Action ID {} does not have a code handler.'
