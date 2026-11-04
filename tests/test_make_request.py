# Copyright (c) 2026 Splunk Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at https://www.apache.org/licenses/LICENSE-2.0

"""Exercise prepared requests and responses without contacting Databricks."""

from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from soar_sdk.exceptions import ActionFailure

from src.app import app
from src.actions import make_request as action


@pytest.fixture
def transport(monkeypatch):
    calls = []
    settings = {"status_code": 200, "body": '{"ok": true}', "error": None}
    authenticate = Mock(return_value={"Authorization": "Bearer test-asset-token"})
    client = Mock()
    client.config.authenticate = authenticate
    client_factory = Mock(return_value=client)
    monkeypatch.setattr(action, "get_client", client_factory)

    def send(_session, request, **kwargs):
        calls.append((request, kwargs))
        if settings["error"]:
            raise settings["error"]
        response = requests.Response()
        response.status_code = settings["status_code"]
        response._content = settings["body"].encode()
        response.encoding = "utf-8"
        response.request = request
        response.headers["Location"] = "https://other.invalid/redirect"
        return response

    monkeypatch.setattr(requests.Session, "send", send)
    return SimpleNamespace(
        calls=calls,
        settings=settings,
        authenticate=authenticate,
        factory=client_factory,
    )


def run(**kwargs):
    params = action.DatabricksMakeRequestParams.model_validate(
        {
            "http_method": "GET",
            "endpoint": "/api/2.0/clusters/spark-versions",
            **kwargs,
        }
    )
    return action.make_request.__wrapped__(
        params, SimpleNamespace(host="https://workspace.example")
    )


@pytest.mark.parametrize(
    "method", ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
)
def test_methods_reuse_asset_authentication(method, transport):
    result = run(http_method=method.lower())
    request, options = transport.calls[0]
    assert request.method == method
    assert request.url == "https://workspace.example/api/2.0/clusters/spark-versions"
    assert request.headers["Authorization"] == "Bearer test-asset-token"
    assert options["timeout"] == 30
    assert options["verify"] is True
    assert options["allow_redirects"] is False
    assert result.status_code == 200
    transport.authenticate.assert_called_once_with()


@pytest.mark.parametrize("status", [200, 201, 204, 302, 400, 401, 403, 404, 429, 500])
def test_http_responses_preserve_status_and_raw_body(status, transport):
    transport.settings.update(
        status_code=status, body="" if status == 204 else "Plain text response"
    )
    output = run()
    assert output.status_code == status
    assert output.response_body == transport.settings["body"]
    assert len(transport.calls) == 1
    assert transport.calls[0][1]["allow_redirects"] is False


@pytest.mark.parametrize(
    "query", ['{"path":"dbfs:/","limit":1}', "path=dbfs%3A%2F&limit=1"]
)
def test_json_and_string_query_parameters(query, transport):
    run(endpoint="api/2.0/dbfs/get-status?existing=yes", query_parameters=query)
    parsed = urlsplit(transport.calls[0][0].url)
    assert parsed.path == "/api/2.0/dbfs/get-status"
    assert parse_qs(parsed.query) == {
        "path": ["dbfs:/"],
        "limit": ["1"],
        "existing": ["yes"],
    }


def test_repeated_and_blank_query_parameters_are_preserved(transport):
    run(query_parameters="?key=first&key=second&empty=")
    parsed = parse_qs(urlsplit(transport.calls[0][0].url).query, keep_blank_values=True)
    assert parsed == {"key": ["first", "second"], "empty": [""]}


def test_json_body_and_custom_headers(transport):
    run(
        http_method="POST",
        body='{"key":[1,null]}',
        headers='{"X-Request-ID":"test"}',
        timeout=7,
        verify_ssl=False,
    )
    request, options = transport.calls[0]
    assert request.body in ('{"key":[1,null]}', b'{"key":[1,null]}')
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["X-Request-ID"] == "test"
    assert options["timeout"] == 7
    assert options["verify"] is False


def test_explicit_non_json_content_type(transport):
    run(http_method="PUT", body="plain text", headers='{"content-type":"text/plain"}')
    request, _ = transport.calls[0]
    assert request.headers["Content-Type"] == "text/plain"
    assert request.body == "plain text"


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://other.invalid/api/2.0/clusters/list",
        "//other.invalid/api/2.0/clusters/list",
        "/api/2.0/../secret",
        "/api/2.0/%2e%2e/secret",
        "/api/2.0/%252e%252e/secret",
        "/api/2.0/./clusters",
        "/api/2.0/\\other",
        "/api/2.0/%5cother",
        "/login",
        "/api/2.0/clusters/list#fragment",
        "/api/2.0/clusters/\nlist",
        "",
    ],
)
def test_invalid_endpoints_never_authenticate_or_send(endpoint, transport):
    with pytest.raises(ActionFailure):
        run(endpoint=endpoint)
    transport.factory.assert_not_called()
    assert not transport.calls


@pytest.mark.parametrize(
    "overrides",
    [
        {"http_method": "TRACE"},
        {"http_method": "CONNECT"},
        {"timeout": 0},
        {"timeout": -1},
        {"headers": "not-json"},
        {"headers": "[]"},
        {"headers": '{"X-Test":1}'},
        {"headers": '{"authorization":"override"}'},
        {"headers": '{"Host":"other.invalid"}'},
        {"headers": '{"Proxy-Authorization":"override"}'},
        {"headers": '{"Cookie":"auth=override"}'},
        {"query_parameters": "[]"},
        {"query_parameters": "null"},
        {"query_parameters": "invalid-query"},
        {"body": "invalid-json"},
        {
            "body": "invalid-json",
            "headers": '{"Content-Type":"application/problem+json"}',
        },
    ],
)
def test_invalid_parameters_fail_before_sending(overrides, transport):
    with pytest.raises(ActionFailure):
        run(**overrides)
    transport.factory.assert_not_called()
    assert not transport.calls


@pytest.mark.parametrize(
    "host",
    [
        "http://workspace.example",
        "https://user:pass@workspace.example",  # pragma: allowlist secret
        "https://workspace.example/path",
        "https://workspace.example?query=x",
        "https://workspace.example:bad",
    ],
)
def test_invalid_asset_host_is_rejected(host, transport):
    params = action.DatabricksMakeRequestParams(
        http_method="GET", endpoint="/api/2.0/clusters/list"
    )
    with pytest.raises(ActionFailure):
        action.make_request.__wrapped__(params, SimpleNamespace(host=host))
    transport.factory.assert_not_called()
    assert not transport.calls


def test_auth_provider_specific_headers_cannot_be_overridden(transport):
    transport.authenticate.return_value = {"X-Vendor-Auth": "secret"}
    with pytest.raises(ActionFailure, match="cannot be overridden"):
        run(headers='{"x-vendor-auth":"override"}')
    assert not transport.calls


@pytest.mark.parametrize(
    "error", [requests.Timeout, requests.ConnectionError, requests.exceptions.SSLError]
)
def test_transport_errors_fail_without_echoing_sensitive_url(error, transport):
    transport.settings["error"] = error("https://workspace.example/?sensitive=value")
    with pytest.raises(ActionFailure, match=error.__name__) as caught:
        run()
    assert "sensitive=value" not in str(caught.value)


def test_missing_asset_authentication_is_a_clear_failure(transport):
    transport.factory.side_effect = ActionFailure("Missing authentication")
    with pytest.raises(ActionFailure, match="Missing authentication"):
        run()
    assert not transport.calls


def test_vendor_auth_configuration_error_is_sanitized(transport):
    transport.factory.side_effect = ValueError("credential configuration details")
    with pytest.raises(ActionFailure, match="Unable to authenticate") as caught:
        run()
    assert "configuration details" not in str(caught.value)
    assert not transport.calls


def test_action_is_registered_with_sdk_request_parameters():
    registered = app.actions_manager.get_action("make_request")
    assert registered.meta.read_only is False
    assert registered.meta.parameters is action.DatabricksMakeRequestParams
    assert registered.meta.action == "make request"
