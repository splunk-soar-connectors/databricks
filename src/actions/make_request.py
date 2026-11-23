# Copyright (c) 2026 Splunk Inc.
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

"""Authenticated HTTP access to Databricks workspace APIs."""

import json
from urllib.parse import parse_qsl, unquote, urlsplit

from soar_sdk.action_results import MakeRequestOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import MakeRequestParams, Param

from ..app import Asset, app
from ..helper import get_client


class DatabricksMakeRequestParams(MakeRequestParams):
    endpoint: str = Param(
        description="Workspace API path, for example /api/2.0/clusters/spark-versions. The asset supplies the host and authentication.",
    )
    timeout: int = Param(
        description="Request timeout in seconds", required=False, default=30
    )


def _request_url(host: str, endpoint: str) -> str:
    message = "endpoint must be a relative Databricks API path beginning with /api/"
    if not endpoint or any(ord(char) < 32 or ord(char) == 127 for char in endpoint):
        raise ActionFailure(message)
    try:
        base = urlsplit(host)
        target = urlsplit(endpoint)
        if (
            base.scheme != "https"
            or not base.hostname
            or base.username is not None
            or base.password is not None
            or base.query
            or base.fragment
            or base.path not in ("", "/")
            or "\\" in host
        ):
            raise ActionFailure(
                "The asset host must be an HTTPS workspace URL without credentials, a path, or a query"
            )
        # Check malformed ports before passing the URL to the HTTP client.
        _ = base.port
    except ValueError as exc:
        raise ActionFailure("Invalid asset host or endpoint URL") from exc
    if target.scheme or target.netloc or "#" in endpoint:
        raise ActionFailure(message)
    path = "/" + target.path.lstrip("/")
    decoded = path
    for _ in range(16):
        next_path = unquote(decoded)
        if next_path == decoded:
            break
        decoded = next_path
    else:
        raise ActionFailure(message)
    if (
        endpoint.startswith("//")
        or "\\" in decoded
        or not decoded.startswith("/api/")
        or any(segment in (".", "..") for segment in decoded.split("/"))
        or any(ord(char) < 32 or ord(char) == 127 for char in decoded)
    ):
        raise ActionFailure(message)
    return f"{base.scheme}://{base.netloc}{path}" + (
        f"?{target.query}" if target.query else ""
    )


def _json_object(value: str | None, name: str) -> dict:
    if value is None or value == "":
        return {}
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError) as exc:
        raise ActionFailure(f"{name} must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise ActionFailure(f"{name} must be a JSON object")
    return parsed


def _query_parameters(value: str | None):
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except ValueError:
        try:
            return parse_qsl(
                value.removeprefix("?"), keep_blank_values=True, strict_parsing=True
            )
        except ValueError as exc:
            raise ActionFailure(
                "query_parameters must be a JSON object or a URL query string"
            ) from exc
    if not isinstance(parsed, dict):
        raise ActionFailure(
            "query_parameters must be a JSON object or a URL query string"
        )
    return parsed


@app.make_request()
def make_request(
    params: DatabricksMakeRequestParams, asset: Asset
) -> MakeRequestOutput:
    """Send an authenticated request to a Databricks workspace API. HTTP error responses are returned as status_code and response_body; transport and input errors fail the action."""
    import requests
    from requests.structures import CaseInsensitiveDict

    url = _request_url(asset.host, params.endpoint)
    method = params.http_method.strip().upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        raise ActionFailure(
            "http_method must be GET, POST, PUT, PATCH, DELETE, HEAD, or OPTIONS"
        )
    if params.timeout <= 0:
        raise ActionFailure("timeout must be a positive integer")
    custom_headers = _json_object(params.headers, "headers")
    if any(not isinstance(value, str) for value in custom_headers.values()):
        raise ActionFailure("headers must contain string values")
    if any(
        name.lower() in {"authorization", "proxy-authorization", "host", "cookie"}
        for name in custom_headers
    ):
        raise ActionFailure(
            "Authentication and Host headers are supplied by the asset and cannot be overridden"
        )
    headers = CaseInsensitiveDict({"Accept": "application/json"})
    headers.update(custom_headers)
    query = _query_parameters(params.query_parameters)
    if params.body is not None:
        headers.setdefault("Content-Type", "application/json")
        content_type = headers["Content-Type"].split(";", 1)[0].strip().lower()
        if content_type == "application/json" or content_type.endswith("+json"):
            try:
                json.loads(params.body)
            except ValueError as exc:
                raise ActionFailure(
                    "body must be valid JSON when Content-Type is JSON"
                ) from exc
    try:
        auth_headers = get_client(asset).config.authenticate()
    except ActionFailure:
        raise
    except Exception as exc:
        raise ActionFailure(
            "Unable to authenticate using the asset configuration"
        ) from exc
    if any(
        name.lower() in {key.lower() for key in auth_headers} for name in custom_headers
    ):
        raise ActionFailure(
            "Authentication headers are supplied by the asset and cannot be overridden"
        )

    def authenticate(request):
        request.headers.update(auth_headers)
        return request

    try:
        with requests.Session() as session:
            session.auth = authenticate
            response = session.request(
                method,
                url,
                headers=headers,
                params=query,
                data=params.body,
                timeout=params.timeout,
                verify=params.verify_ssl,
                allow_redirects=False,
            )
            return MakeRequestOutput(
                status_code=response.status_code, response_body=response.text
            )
    except requests.RequestException as exc:
        # Exception text may contain a URL with user-supplied sensitive query parameters.
        raise ActionFailure(f"HTTP request failed ({type(exc).__name__})") from exc
