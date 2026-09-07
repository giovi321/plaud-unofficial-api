---
title: How the API works
description: Regional routing, the data and authentication endpoints, and the response shapes the client normalises.
---

Plaud exposes an undocumented REST API. All requests are authenticated with a `Bearer` token in the `Authorization` header.

## Regional routing

Plaud shards accounts across dedicated regional API hosts. `api.plaud.ai` is a **discovery** host that rejects region-pinned tokens with `status: -302` / `msg: "user region mismatch"` and returns the correct host. The region is encoded in the token's `region` claim and mapped to a host:

| `region` claim | API host | | `region` claim | API host |
|----------------|----------|---|----------------|----------|
| `aws:eu-central-1` | `api-euc1.plaud.ai` | | `aws:us-west-1` | `api-usw1.plaud.ai` |
| `aws:eu-west-1` | `api-euw1.plaud.ai` | | `aws:us-west-2` | `api-usw2.plaud.ai` |
| `aws:us-east-1` | `api-use1.plaud.ai` | | `aws:ap-southeast-1` | `api-apse1.plaud.ai` |
| `aws:us-east-2` | `api-use2.plaud.ai` | | `aws:ap-southeast-2` | `api-apse2.plaud.ai` |
| `aws:ap-northeast-1` | `api-apne1.plaud.ai` | | `aws:ap-south-1` | `api-aps1.plaud.ai` |

The client handles this automatically:

1. On startup, **only if `api_base` is left at the default discovery host**, it reads the `region` claim from your token and routes to the matching regional host. An explicit `plaud config set-api` override is always respected.
2. If a request still hits a `-302`, it follows the host the API returns in `data.domains.api` and retries **once**. The server's host is authoritative and wins over the token's region claim, which can be **stale** after an account migration (e.g. a token issued as `aws:us-west-2` whose data now lives in `aws:eu-central-1`). Only `*.plaud.ai` hosts are accepted as redirect targets; if the body omits a host it falls back to the token's region claim.

## Data endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/file/simple/web` | `GET` | List all recordings (summary objects). |
| `/file/list` | `POST` | Full detail for one or more recordings (body: `["file_id"]`). Returns `trans_result` and `ai_content` inline. |
| `/file/detail/{id}` | `GET` | Full detail for one recording (may omit transcript). |
| `content_list[].data_link` | `GET` | Signed URL for transcript, AI summary, or recording. |

**Response envelope:** the API wraps responses in different shapes depending on the endpoint. `api.py` normalises all variants, looking for the payload under `payload`, `data`, `data_file_list`, or at the root; `status` of `0`/`200`/`ok`/`success` is a success.

**Content hydration:** the client first tries `POST /file/list`, which returns transcript data (`trans_result`) inline as speaker-labelled segments. If that fails or returns incomplete data, it falls back to `GET /file/detail/{id}` and fetches transcript/summary from signed URLs in the `content_list` array.

## Retry on transient failures

Every request retries connection errors, read timeouts, DNS failures, `429` and `5xx` three times, waiting 1s then 2s (capped at 8s). Other `4xx` responses and malformed payloads fail on the first response, so an auth or not-found error stays fast.

This exists because a single dropped request used to abort a whole run. On a scheduled sync the practical consequence was a hard failure, and an alert, for something the next run resolved by itself. A request can now take up to roughly three times the 30s client timeout before giving up, so a scheduled caller should be single-instance guarded. See [Keeping an unattended sync alive](/plaud-unofficial-api/guides/unattended-sync/).

## Authentication endpoints

The bearer token is minted by the web app's own (undocumented) auth endpoints, on the **regional** host (they follow the same `-302` redirect as the data endpoints):

| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `/auth/access-token` | `POST` | form-encoded `username` (the email) + `password` | `{access_token, refresh_token, token_type, …}` |
| `/auth/otp-send-code` | `POST` | JSON `{username, user_area}` | `{token}` |
| `/auth/otp-login` | `POST` | JSON `{code, token, user_area}` | `{access_token, token_type}` |

This CLI implements only the **email + password** flow (`/auth/access-token`). Two non-obvious details:

- The login request must be sent with a **minimal** header set. Sending the full browser-fingerprint headers the data endpoints use makes the login endpoint return a *success envelope with an empty `access_token`* (a stub). The client therefore sends only `Content-Type`, `Accept`, `Origin`, and `Referer` for login.
- The response carries a `refresh_token`, but the CLI **ignores** it and re-mints from your stored credentials instead.

Plaud's **official, supported** API is different: an OAuth 2.0 client-credentials surface at `platform-<region>.plaud.ai/developer/api` (with real refresh tokens), currently in private beta — see the [developer platform](https://www.plaud.ai/pages/developer-platform). It is unrelated to the web token this CLI uses.
