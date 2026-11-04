## Authentication

Configure this connector with a Databricks personal access token (PAT) in the `token` asset field.

Databricks retired Databricks-managed username/password (basic) authentication for its UI and APIs on **July 10, 2024**. See **End of life for Databricks-managed passwords** in the [official July 2024 release notes](https://docs.databricks.com/aws/en/release-notes/product/2024/july#end-of-life-for-databricks-managed-passwords).

To generate and configure a PAT:

1. Navigate to your Databricks instance and log in.
1. Click on your profile picture in the top right, and click on `Settings`.
1. Click `Developer` in the menu on left. Next to `Access tokens`, click `Manage`.
1. Click `Generate token`. Give your token a name and lifespan, and save it.
1. Copy the token, and enter it in the `token` field when configuring the connector. Leave the `username` and `password` fields blank.

### SDK migration

This version uses the Splunk SOAR SDK and requires SOAR 7.0 or later with Python 3.13 or 3.14. Existing asset fields and per-alert ingestion checkpoints are retained. SQL result rows are represented as a matrix, matching the Databricks API; use `result.data_array.*.*` to access individual cells. Complex values in string fields (including query parameter date ranges) are JSON encoded.

Query actions use standard tables with Statement Id, Query State, and Rows Returned columns. SQL result rows and schema remain in the action outputs.

Polling retains the legacy `containers_saved` and `save_failures` summary fields, including counts for partial failures. Alert checkpoints are committed only after a successful poll; a failed poll is retried without advancing its checkpoints.

### Make request

Use **make request** to call workspace API endpoints that do not have a dedicated action. The action uses the asset host and authentication. Supply a relative path such as `/api/2.0/clusters/spark-versions`; a leading slash is optional. Absolute URLs, fragments, path traversal, and authentication/Host header overrides are rejected. Redirects are returned without being followed.

Supported methods are GET, POST, PUT, PATCH, DELETE, HEAD, and OPTIONS. Headers must be a JSON object with string values. Query parameters accept a JSON object or a URL query string, including repeated keys. A body defaults to JSON; set Content-Type explicitly for another text format. Timeout defaults to 30 seconds and TLS certificate verification defaults to enabled.

The output contains `status_code` and `response_body`, including for HTTP 4xx/5xx responses. A completed HTTP exchange is an action success; playbooks must check `status_code` to determine whether the API operation succeeded. Invalid input and transport failures fail the action. Write methods have the same effect and permissions as direct Databricks API calls.
