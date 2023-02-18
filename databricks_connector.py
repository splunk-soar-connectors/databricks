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

import phantom.app as phantom
import requests
from databricks_cli.sdk.api_client import ApiClient
from phantom.action_result import ActionResult
from phantom.base_connector import BaseConnector

import databricks_consts as consts
from databricks_enums import DatabricksEndpoint


class DatabricksConnector(BaseConnector):

    def __init__(self):
        super(DatabricksConnector, self).__init__()

        self._state = None

        self._host = None
        self._username = None
        self._password = None
        self._token = None

    def _get_error_msg_from_exception(self, exception):
        error_code = consts.DATABRICKS_ERROR_CODE_UNAVAILABLE
        error_message = consts.DATABRICKS_ERROR_MESSAGE_UNAVAILABLE

        self.error_print(traceback.format_exc())

        try:
            if exception.args:
                if len(exception.args) > 1:
                    error_code = exception.args[0]
                    error_message = exception.args[1]
                    return f'Error Code: {error_code}. Error Message: {error_message}'

                if len(exception.args) == 1:
                    error_message = exception.args[0]
        except Exception:
            pass

        return f'Error Message: {error_message}'

    def _get_api_client(self):
        api_client = ApiClient(
            host=self._host,
            user=self._username,
            password=self._password,
            token=self._token,
        )
        return api_client

    def _handle_test_connectivity(self, param):
        self.save_progress(consts.TEST_CONNECTIVITY_PROGRESS_MESSAGE)

        action_result = self.add_action_result(ActionResult(dict(param)))

        try:
            # TODO
            self.save_progress(consts.TEST_CONNECTIVITY_SUCCESS_MESSAGE)
            return action_result.set_status(phantom.APP_SUCCESS)
        except Exception as e:
            self.save_progress(self._get_error_msg_from_exception(e))
            return action_result.set_status(phantom.APP_ERROR, consts.TEST_CONNECTIVITY_ERROR_MESSAGE)

    def _handle_create_alert(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        action_result = self.add_action_result(ActionResult(dict(param)))
        api_client = self._get_api_client()

        data = {}
        data['name'] = param['name']
        data['query_id'] = param['query_id']
        data['options'] = {
            'column': param['column'],
            'custom_body': param.get('custom_body'),
            'custom_subject': param.get('custom_subject'),
            'muted': param.get('muted'),
            'op': param['operator'],
            'schedule_failures': param.get('schedule_failures'),
            'value': param['value'],
        }
        # Clear null options
        data['options'] = {option: value for option, value in data['options'].items() if value is not None}

        rearm = param.get('rearm')
        if rearm is not None:
            data['rearm'] = rearm

        data['parent'] = param['parent']

        try:
            result = api_client.perform_query(**DatabricksEndpoint.CREATE_ALERT.api_info, data=data)
            action_result.add_data(result)
        except Exception as e:
            error_message = self._get_error_msg_from_exception(e)
            return action_result.set_status(phantom.APP_ERROR, error_message)

        summary = {
            'status': 'Successfully created alert',
        }
        action_result.update_summary(summary)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_delete_alert(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

        action_result = self.add_action_result(ActionResult(dict(param)))
        api_client = self._get_api_client()

        alert_id = param['alert_id']

        try:
            api_info = DatabricksEndpoint.DELETE_ALERT.api_info_with_interpolation(alert_id=alert_id)
            result = api_client.perform_query(**api_info)
            action_result.add_data(result)
        except Exception as e:
            error_message = self._get_error_msg_from_exception(e)
            return action_result.set_status(phantom.APP_ERROR, error_message)

        summary = {
            'status': 'Successfully deleted alert',
        }
        action_result.update_summary(summary)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_perform_query(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

    def _handle_execute_notebook(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

    def _handle_on_poll(self, param):
        self.debug_print(f'In action handler for: {self.get_action_identifier()}')

    def handle_action(self, param):
        # Get the action that we are supposed to execute for this App Run
        action_id = self.get_action_identifier()

        self.debug_print("action_id", self.get_action_identifier())

        if action_id == 'test_connectivity':
            ret_val = self._handle_test_connectivity(param)
        elif action_id == 'create_alert':
            ret_val = self._handle_create_alert(param)
        elif action_id == 'delete_alert':
            ret_val = self._handle_delete_alert(param)
        elif action_id == 'perform_query':
            ret_val = self._handle_perform_query(param)
        elif action_id == 'execute_notebook':
            ret_val = self._handle_execute_notebook(param)
        elif action_id == 'on_poll':
            ret_val = self._handle_on_poll(param)
        else:
            action_result = self.add_action_result(ActionResult(dict(param)))
            ret_val = action_result.set_status(phantom.APP_ERROR,
                                               consts.UNHANDLED_ACTION_ID_ERROR_MESSAGE.format(action_id))

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
