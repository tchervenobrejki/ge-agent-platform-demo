# Example: an agent that reads HubSpot over MCP

A small [ADK](https://adk.dev/) agent that answers questions about a HubSpot CRM through
HubSpot's own [remote MCP server](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/integrate-with-the-remote-hubspot-mcp-server),
**as the signed-in HubSpot user**, and read-only.

It is separate from the growth & risk agents in this repository. They call an MCP server *you* run, with a
service identity (see [notebook 03](../../notebooks/03_rag_and_mcp.ipynb)). This one calls a *vendor's* MCP server
on behalf of a person, with OAuth, which is how most SaaS MCP servers work. HubSpot is the example; the pattern
carries over to any OAuth-protected MCP server.

**Step by step, with every command explained: [notebook 10](../../notebooks/10_hubspot_mcp.ipynb).**

## The pattern

| Step | For HubSpot | In general |
|---|---|---|
| 1. Discover how to sign in | `https://mcp.hubspot.com` answers 401 and points to its OAuth metadata: PKCE with S256, secret sent as `client_secret_post` | `/.well-known/oauth-protected-resource` ([RFC 9728](https://www.rfc-editor.org/rfc/rfc9728)) and `/.well-known/oauth-authorization-server` ([RFC 8414](https://www.rfc-editor.org/rfc/rfc8414)) |
| 2. Register a client | *Development → MCP Auth Apps → Create MCP auth app*, with the redirect URL `http://localhost:8000/dev-ui/` | the vendor's developer console; note the client ID, secret and redirect URLs |
| 3. Store the secret | Secret Manager, `hubspot-mcp-client-secret` | never in code, `.env` or a notebook |
| 4. Connect the agent | `McpToolset` with `auth_scheme` (OAuth2 authorization code) and `auth_credential` (client ID, secret, redirect, PKCE) | the same; ADK runs the sign-in, keeps the token and sends it as a Bearer header |
| 5. Restrict it | allow-listed read tools, object types and fields | whatever that server's tools expose beyond what the agent needs |
| 6. Approve and sign in | a Super Admin approves the app once; each user clicks **Allow** | the vendor's admin consent, then user consent |

## Why the agent restricts itself

With user sign-in, the agent can never see more than the user could, but it can see everything the user can.
HubSpot's MCP auth apps have no scope list: HubSpot grants what the server's tools need, limited by the user's
permissions, and the server also has write tools. So [`hubspot_agent/agent.py`](hubspot_agent/agent.py) narrows
it down in three layers:

1. **`tool_filter`**: an allow-list of four read tools. Write tools, and tools HubSpot adds later, are never loaded.
2. **`before_tool_callback`**: calls may only read companies, contacts, deals and notes, and only listed fields.
   When no fields are named it asks for the allowed ones, because HubSpot's defaults include a deal's amount.
3. **`after_tool_callback`**: drops any other field from responses before the model sees them, and fails closed if
   a response can't be checked.

## Run it

You need a Google Cloud project with Gemini access, `gcloud auth application-default login`,
[uv](https://docs.astral.sh/uv/), and a HubSpot account in which you can create an MCP auth app.

```bash
cd examples/hubspot-mcp
uv sync
uv run pytest                     # offline: the policy, and the sign-in request (PKCE)
```

Then configure it, either with [notebook 10](../../notebooks/10_hubspot_mcp.ipynb) (recommended: it also checks
HubSpot's metadata and stores the secret), or by hand:

```bash
gcloud services enable secretmanager.googleapis.com
printf '%s' 'YOUR_CLIENT_SECRET' | gcloud secrets create hubspot-mcp-client-secret --data-file=-
cp .env.example .env              # then fill in GOOGLE_CLOUD_PROJECT and HUBSPOT_CLIENT_ID
```

(Typing the secret into a command leaves it in your shell history; the notebook uses a hidden prompt instead.)

Start the dev UI on port 8000, which matches the redirect URL:

```bash
uv run adk web --port 8000 .
```

Open http://localhost:8000/dev-ui/?app=hubspot_agent (`localhost`, not `127.0.0.1`) and ask *Who am I in
HubSpot?* The agent asks you to sign in; a HubSpot window opens; click **Allow**.

## Files

| File | What it is |
|---|---|
| [`hubspot_agent/agent.py`](hubspot_agent/agent.py) | the agent, the MCP toolset with OAuth, and the three policy layers |
| [`hubspot_agent/__init__.py`](hubspot_agent/__init__.py) | loads `.env` before the agent reads its settings |
| [`tests/test_agent.py`](tests/test_agent.py) | offline tests |
| [`.env.example`](.env.example) | the settings, without secrets |

## Limits

- Tested locally with `adk web`. For a deployed agent, inject the secret from Secret Manager as
  `HUBSPOT_CLIENT_SECRET` and set `HUBSPOT_REDIRECT_URI` to the client that runs the sign-in. Gemini Enterprise
  runs the sign-in itself through an *authorization* resource; HubSpot's app then also needs
  `https://vertexaisearch.cloud.google.com/oauth-redirect` and
  `https://vertexaisearch.cloud.google.com/static/oauth/oauth.html` as redirect URLs. That path isn't covered here.
- HubSpot's tool names and arguments may change; the tool allow-list logs every tool it skips, so new ones show up.
