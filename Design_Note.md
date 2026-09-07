# Engineering Design Note: GitHub Issues Gateway

## 1. Error Mapping Strategy
- Upstream GitHub API status codes (401, 403, 404, 422) are mapped into standardized JSON error objects containing `message`, `status_code`, and `timestamp`.
- 400 Bad Request is returned for invalid local payloads before hitting GitHub.

## 2. Pagination Strategy
- Forwarding of GitHub's `Link` response header on `GET /issues`.
- Accepts `page` and `per_page` (max 100) query parameters and propagates them downstream to GitHub REST endpoints.

## 3. Webhook Deduplication & Idempotency
- Incoming payloads rely on `X-GitHub-Delivery` GUID header as primary deduplication key in local SQLite store.
- Re-processing existing delivery IDs results in a quick `204 No Content` acknowledgement without re-writing state.

## 4. Security Trade-offs & HMAC Verification
- Webhook HMAC SHA-256 signatures are calculated over raw request bodies using `WEBHOOK_SECRET` and compared via `hmac.compare_digest` (constant-time) to eliminate timing attacks.
- Sensitive environment variables (`GITHUB_TOKEN`, `WEBHOOK_SECRET`) are loaded strictly from `.env` and excluded from git tracking.
