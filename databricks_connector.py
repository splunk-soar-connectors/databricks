# File: databricks_connector.py
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

import json
import traceback
from datetime import datetime
from time import sleep

import phantom.app as phantom
import requests
from databricks_cli.sdk import DbfsService, JobsService
from databricks_cli.sdk.api_client import ApiClient
from phantom.action_result import ActionResult
from phantom.base_connector import BaseConnector

import databricks_consts as consts
from databricks_enums import DatabricksEndpoint


class RetVal(tuple):
    def __new__(cls, val1, val2=None):
        return tuple.__new__(RetVal, (val1, val2))


class DatabricksConnector(BaseConnector):

    def __init__(self):
        super(DatabricksConnector, self).__init__()

        self._state = None

        self._host = None
        self._username = None
        self._password = None
        self._token = None

    def _get_error_msg_from_exception(self, e):

        error_code = None
        error_message = consts.DATABRICKS_ERROR_MESSAGE_UNAVAILABLE

        self.error_print(traceback.format_exc())

        try:
            if hasattr(e, "args"):
                if len(e.args) > 1:
                    error_code = e.args[0]
                    error_message = e.args[1]
                elif len(e.args) == 1:
                    error_message = e.args[0]
        except Exception as e:
            self.error_print("Error occurred while fetching exception information. Details: {}".format(str(e)))

        if not error_code:
            error_text = "Error Message: {}".format(error_message)
        else:
            error_text = "Error Code: {}. Error Message: {}".format(error_code, error_message)

        return error_text

    @staticmethod
    def _set_key_if_param_defined(dict_to_update: dict,
                                  param: dict,
                                  key: str,
                                  is_json: bool = False,
                                  param_key: str = None):
        if param_key is None:
            param_key = key

        if param_key not in param:
            return

        if is_json:
            value = json.loads(param[param_key])
        else:
            value = param[param_key]

        dict_to_update[key] = value

    def _get_api_client(self):
        api_client = ApiClient(
            host=self._host,
            user=self._username,
            password=self._password,
            token=self._token,
        )

        # Override user agent to {ISV Name}-{Product Name} per Databricks best practices
        api_client.default_headers['user-agent'] = 'splunk-soar'

        return api_client

    def _handle_test_connectivity(self, param):
        self.save_progress(consts.TEST_CONNECTIVITY_PROGRESS_MESSAGE)

        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            api_client = self._get_api_client()
            dbfs_service = DbfsService(api_client)
            dbfs_service.get_status(consts.TEST_CONNECTIVITY_FILE_PATH)

            self.save_progress(consts.TEST_CONNECTIVITY_SUCCESS_MESSAGE)
            return action_result.set_status(phantom.APP_SUCCESS)
        except Exception as e:
            error_msg = self._get_error_msg_from_exception(e)
            self.save_progress(error_msg)
            return action_result.set_status(phantom.APP_ERROR, consts.TEST_CONNECTIVITY_ERROR_MESSAGE)

    def _handle_create_alert(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        action_result = self.add_action_result(ActionResult(dict(param)))

        data = {}
        data['name'] = param['name']
        data['query_id'] = param['query_id']

        options = {
            'column': param['column'],
            'op': param['operator'],
            'value': param['value'],
        }
        self._set_key_if_param_defined(options, param, 'custom_body')
        self._set_key_if_param_defined(options, param, 'custom_subject')
        self._set_key_if_param_defined(options, param, 'muted')
        self._set_key_if_param_defined(options, param, 'schedule_failures')
        data['options'] = options

        self._set_key_if_param_defined(data, param, 'rearm')
        self._set_key_if_param_defined(data, param, 'parent')

        try:
            api_client = self._get_api_client()
            result = api_client.perform_query(**DatabricksEndpoint.CREATE_ALERT.api_info, data=data)
            action_result.add_data(result)
            summary = {
                'status': consts.CREATE_ALERT_SUCCESS_MESSAGE,
            }
            action_result.update_summary(summary)
            return action_result.set_status(phantom.APP_SUCCESS)

        except Exception as e:
            self.save_progress(self._get_error_msg_from_exception(e))
            return action_result.set_status(phantom.APP_ERROR, consts.CREATE_ALERT_ERROR_MESSAGE)

    def _handle_list_alerts(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            api_client = self._get_api_client()
            api_info = DatabricksEndpoint.LIST_ALERTS.api_info_with_interpolation()
            result = api_client.perform_query(**api_info)

            for item in result:
                action_result.add_data(item)

            summary = {
                'status': consts.LIST_ALERTS_SUCCESS_MESSAGE,
                'Total alerts': len(result)
            }

            action_result.update_summary(summary)
            return action_result.set_status(phantom.APP_SUCCESS)

        except Exception as e:
            error_message = self._get_error_msg_from_exception(e)
            return action_result.set_status(phantom.APP_ERROR, consts.LIST_ALERTS_ERROR_MESSAGE, error_message)

    def _handle_list_clusters(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            api_client = self._get_api_client()
            api_info = DatabricksEndpoint.LIST_CLUSTERS.api_info_with_interpolation()
            result = api_client.perform_query(**api_info)
            total_clusters = 0

            if 'clusters' in result:
                for cluster in result['clusters']:
                    action_result.add_data(cluster)
                total_clusters = len(result['clusters'])

            summary = {
                'status': consts.LIST_CLUSTERS_SUCCESS_MESSAGE,
                'Total Clusters': total_clusters
            }

            action_result.update_summary(summary)
            return action_result.set_status(phantom.APP_SUCCESS)

        except Exception as e:
            error_message = self._get_error_msg_from_exception(e)
            return action_result.set_status(phantom.APP_ERROR, consts.LIST_CLUSTERS_ERROR_MESSAGE, error_message)

    def _handle_delete_alert(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            api_client = self._get_api_client()

            alert_id = param['alert_id']

            api_info = DatabricksEndpoint.DELETE_ALERT.api_info_with_interpolation(alert_id=alert_id)
            result = api_client.perform_query(**api_info)
            action_result.add_data(result)

            summary = {
                'status': consts.DELETE_ALERT_SUCCESS_MESSAGE,
            }
            action_result.update_summary(summary)

            # also remove from state file if present
            if 'alerts' in self._state and alert_id in self._state['alerts']:
                del self._state['alerts'][alert_id]

            return action_result.set_status(phantom.APP_SUCCESS)

        except Exception as e:
            error_message = self._get_error_msg_from_exception(e)
            return action_result.set_status(phantom.APP_ERROR, consts.DELETE_ALERT_ERROR_MESSAGE, error_message)

    def _handle_perform_query(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            api_client = self._get_api_client()
            data = {}
            data['statement'] = param['statement']
            data['warehouse_id'] = param['warehouse_id']

            if 'wait_timeout' in param:
                data['wait_timeout'] = f'{param["wait_timeout"]}s'

            self._set_key_if_param_defined(data, param, 'byte_limit')
            self._set_key_if_param_defined(data, param, 'catalog')
            self._set_key_if_param_defined(data, param, 'disposition')
            self._set_key_if_param_defined(data, param, 'format')
            self._set_key_if_param_defined(data, param, 'on_wait_timeout')
            self._set_key_if_param_defined(data, param, 'schema')

            result = api_client.perform_query(**DatabricksEndpoint.PERFORM_QUERY.api_info, data=data)
            action_result.add_data(result)

            summary = {
                'status': consts.PERFORM_QUERY_SUCCESS_MESSAGE,
            }
            action_result.update_summary(summary)

            return action_result.set_status(phantom.APP_SUCCESS)

        except Exception as e:
            error_message = self._get_error_msg_from_exception(e)
            return action_result.set_status(phantom.APP_ERROR, consts.PERFORM_QUERY_ERROR_MESSAGE, error_message)

    def _handle_get_job_run(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        action_result = self.add_action_result(ActionResult(dict(param)))

        run_id = param.get('run_id')

        ret_val, response = self._get_job_run(run_id, action_result)
        action_result.add_data(response)

        if phantom.is_fail(ret_val):
            return ret_val

        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_job_run(self, run_id, action_result):
        self.debug_print('Getting job run')

        try:
            api_client = self._get_api_client()
            api_info = DatabricksEndpoint.JOB_RUN.api_info_with_interpolation(run_id=run_id)
            result = api_client.perform_query(**api_info)

        except Exception as e:
            error_msg = self._get_error_msg_from_exception(e)

            return RetVal(action_result.set_status(phantom.APP_ERROR, 'Job run error: {}'.format(error_msg)), None)

        return RetVal(phantom.APP_SUCCESS, result)

    def _handle_get_job_output(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        action_result = self.add_action_result(ActionResult(dict(param)))

        run_id = param.get('run_id')

        try:
            api_client = self._get_api_client()
            api_info = DatabricksEndpoint.JOB_RUN_OUTPUT.api_info_with_interpolation(run_id=run_id)
            result = api_client.perform_query(**api_info)

        except Exception as e:
            error_msg = self._get_error_msg_from_exception(e)

            return RetVal(action_result.set_status(phantom.APP_ERROR, 'Job run output error: {}'.format(error_msg)), None)

        action_result.add_data(result)
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_execute_notebook(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            api_client = self._get_api_client()
            jobs_service = JobsService(api_client)

            task_info = {}
            # Task key needs to be unique per parent job and can be used to set a dependency order
            # within a job. However, for the purposes of this action we always create a one time job
            # with a single task, so we can hardcode a readable value instead of exposing this detail
            # to the user.
            task_info['task_key'] = 'soar_execute_notebook_action'
            task_info['notebook_path'] = param['notebook_path']
            self._set_key_if_param_defined(task_info, param, 'new_cluster', is_json=True)
            self._set_key_if_param_defined(task_info, param, 'libraries', is_json=True)

            run_info = {}
            run_info['notebook_task'] = task_info
            self._set_key_if_param_defined(run_info, param, 'existing_cluster_id')
            self._set_key_if_param_defined(run_info, param, 'git_source', is_json=True)
            self._set_key_if_param_defined(run_info, param, 'timeout_seconds')
            self._set_key_if_param_defined(run_info, param, 'run_name')
            self._set_key_if_param_defined(run_info, param, 'idempotency_token')
            self._set_key_if_param_defined(run_info, param, 'access_control_list', is_json=True)

            result = jobs_service.submit_run(**run_info)

            sleep(consts.EXECUTE_NOTEBOOK_SLEEP_TIME_IN_SECONDS)

            if 'run_id' in result:
               ret_val, response = self._get_job_run(result['run_id'], action_result)
            else:
                return action_result.set_status(phantom.APP_ERROR, 'Failed to retrieve run_id: {}'.format(result['run_id']))

            action_result.add_data(response)

            result_state = response.get('state', {}).get('result_state', {})
            state_message = response.get('state', {}).get('state_message', {})

            if result_state == 'FAILED':

                summary = {
                    'status': consts.EXECUTE_NOTEBOOK_ERROR_MESSAGE
                }
                action_result.update_summary(summary)
                return action_result.set_status(phantom.APP_ERROR, state_message)

            summary = {
                'status': consts.EXECUTE_NOTEBOOK_SUCCESS_MESSAGE
            }
            action_result.update_summary(summary)
            return action_result.set_status(phantom.APP_SUCCESS)

        except Exception as e:
            error_message = self._get_error_msg_from_exception(e)
            return action_result.set_status(phantom.APP_ERROR, consts.EXECUTE_NOTEBOOK_ERROR_MESSAGE, error_message)

    def _handle_list_warehouses(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            api_client = self._get_api_client()
            api_info = DatabricksEndpoint.LIST_WAREHOUSES.api_info_with_interpolation()
            result = api_client.perform_query(**api_info)
            total_warehouses = 0

            if 'warehouses' in result:
                for warehouse in result['warehouses']:
                    action_result.add_data(warehouse)
                total_warehouses = len(result['warehouses'])

            summary = {
                'status': consts.LIST_WAREHOUSES_SUCCESS_MESSAGE,
                'total warehouses': total_warehouses
            }

            action_result.update_summary(summary)
            return action_result.set_status(phantom.APP_SUCCESS)

        except Exception as e:
            error_message = self._get_error_msg_from_exception(e)
            return action_result.set_status(phantom.APP_ERROR, consts.LIST_WAREHOUSES_ERROR_MESSAGE, error_message)

    def _date_compare(self, alert_triggered_date, last_triggered_date):
        if datetime.strptime(alert_triggered_date, consts.DATETIME_FORMAT) > datetime.strptime(last_triggered_date, consts.DATETIME_FORMAT):
            return True
        else:
            return False

    def _handle_on_poll(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        if self.is_poll_now():
            self.debug_print("Starting polling now")
            pass

        # config = self.get_config()
        action_result = self.add_action_result(ActionResult(dict(param)))

        api_client = self._get_api_client()

        api_info = DatabricksEndpoint.LIST_ALERTS.api_info_with_interpolation()
        result = api_client.perform_query(**api_info)

        # get list of alerts from state to compare to current list of alerts
        state_alerts = self._state.get("alerts", {})

        for alert in result:
            last_triggered_at = alert.get('last_triggered_at')
            if not last_triggered_at:
                continue

            alert_id = alert.get('id')

            # check to see if the latest alert trigger date is later than the last time it triggered
            if alert_id:
                if alert_id in state_alerts and not self._date_compare(last_triggered_at, state_alerts[alert_id]):
                    continue

                state_alerts[alert_id] = last_triggered_at

                container = dict()
                container['name'] = alert.get('name', 'Databricks Alert')
                container['artifacts'] = [{'cef': alert }]
                self.save_container(container)

                self._state['alerts'] = state_alerts

        return action_result.set_status(phantom.APP_SUCCESS)

    def handle_action(self, param):
        # Get the action that we are supposed to execute for this App Run
        action_id = self.get_action_identifier()

        self.debug_print("action_id", self.get_action_identifier())

        try:
            if action_id == 'test_connectivity':
                ret_val = self._handle_test_connectivity(param)
            elif action_id == 'list_alerts':
                ret_val = self._handle_list_alerts(param)
            elif action_id == 'list_clusters':
                ret_val = self._handle_list_clusters(param)
            elif action_id == 'create_alert':
                ret_val = self._handle_create_alert(param)
            elif action_id == 'delete_alert':
                ret_val = self._handle_delete_alert(param)
            elif action_id == 'get_job_run':
                ret_val = self._handle_get_job_run(param)
            elif action_id == 'get_job_output':
                ret_val = self._handle_get_job_output(param)
            elif action_id == 'perform_query':
                ret_val = self._handle_perform_query(param)
            elif action_id == 'execute_notebook':
                ret_val = self._handle_execute_notebook(param)
            elif action_id == 'list_warehouses':
                ret_val = self._handle_list_warehouses(param)
            elif action_id == 'on_poll':
                ret_val = self._handle_on_poll(param)
            else:
                action_result = self.add_action_result(ActionResult(dict(param)))
                ret_val = action_result.set_status(phantom.APP_ERROR,
                                                   consts.UNHANDLED_ACTION_ID_ERROR_MESSAGE.format(action_id))
        except Exception as e:
            error_message = self._get_error_msg_from_exception(e)
            action_result = self.add_action_result(ActionResult(dict(param)))
            ret_val = action_result.set_status(phantom.APP_ERROR, error_message)

        return ret_val

    def initialize(self):
        # Load the state in initialize, use it to store data
        # that needs to be accessed across actions
        self._state = self.load_state()

        # get the asset config
        config = self.get_config()

        self._host = config['host']
        self._username = config.get('username')
        self._password = config.get('password')
        self._token = config.get('token')

        if not (self._username and self._password) and not self._token:
            return self.set_status(phantom.APP_ERROR, consts.MISSING_AUTHENTICATION_ERROR_MESSAGE)

        return phantom.APP_SUCCESS

    def finalize(self):
        # Save the state, this data is saved across actions and app upgrades
        self.save_state(self._state)
        return phantom.APP_SUCCESS


def main():
    import argparse

    import pudb
    pudb.set_trace()

    argparser = argparse.ArgumentParser()

    argparser.add_argument('input_test_json', help='Input Test JSON file')
    argparser.add_argument('-u', '--username', help='username', required=False)
    argparser.add_argument('-p', '--password', help='password', required=False)
    argparser.add_argument('-v', '--verify', help='verify', default=False)

    args = argparser.parse_args()
    session_id = None

    username = args.username
    password = args.password

    if username is not None and password is None:
        # User specified a username but not a password, so ask
        import getpass
        password = getpass.getpass("Password: ")

    if username and password:
        try:
            login_url = DatabricksConnector._get_phantom_base_url() + '/login'

            print("Accessing the Login page")
            r = requests.get(login_url, verify=args.verify)
            csrftoken = r.cookies['csrftoken']

            data = dict()
            data['username'] = username
            data['password'] = password
            data['csrfmiddlewaretoken'] = csrftoken

            headers = dict()
            headers['Cookie'] = 'csrftoken=' + csrftoken
            headers['Referer'] = login_url

            print("Logging into Platform to get the session id")
            r2 = requests.post(login_url, verify=False, data=data, headers=headers)
            session_id = r2.cookies['sessionid']
        except Exception as e:
            print("Unable to get session id from the platform. Error: " + str(e))
            exit(1)

    with open(args.input_test_json) as f:
        in_json = f.read()
        in_json = json.loads(in_json)
        print(json.dumps(in_json, indent=4))

        connector = DatabricksConnector()
        connector.print_progress_message = True

        if session_id is not None:
            in_json['user_session_token'] = session_id
            connector._set_csrf_info(csrftoken, headers['Referer'])

        ret_val = connector._handle_action(json.dumps(in_json), None)
        print(json.dumps(json.loads(ret_val), indent=4))

    exit(0)


if __name__ == '__main__':
    main()
