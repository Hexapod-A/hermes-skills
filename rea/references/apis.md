# APIs (HTTP, GraphQL, RPC)

## Observe

- Your own app or one you are allowed to test: export a HAR from the browser DevTools (Network ->
  Save all as HAR), or run `mitmproxy` / `mitmweb` and point the app at it. Save the flows.
- Public API with docs: read the docs, then check every claim against real responses. Docs drift.
- Probe in this order: happy path, same request twice, missing each field, wrong type for each
  field, boundary values, unknown ids, wrong method, unknown path, bad JSON, empty body, big body,
  no auth / bad auth (only on your own account), pagination ends, sort orders.
- Record what the fields depend on: time, user, locale, headers (`Accept`, `Accept-Language`),
  query order, idempotency keys.

## Specify

For each endpoint: method, path, params, body schema with types and limits, every status code and
its exact error body, headers that matter (`Content-Type`, `Allow`, `Location`, cache headers),
ordering of validation (which error wins when two fields are bad), and the maths (rounding mode,
units such as kobo/cents, currency formatting).

## Test

- `target-http.json`: `headers_keep` lists headers to compare (keep `content-type`; add `allow`,
  `location`, `cache-control` when they matter). Redirects are recorded, not followed.
- Compare `status`, `headers`, `body` exactly. Mask ids/timestamps by format with `rules.mask`.
- Use `unordered` only when the original's order really is unstable (call it twice to check).
- Property cases: random valid and invalid bodies from `fields`; boundaries from the same specs;
  `fixed_cases` for wrong JSON types (string for int, float for int, bool, list body, invalid JSON).
- Validation order bugs show up as `status` clusters in triage with two bad fields in the input.

## Rebuild

OpenAPI first (write the schema from observations), then the server or client. For clients, the
"original" target is the real API (rate-limit your runs) and the replica is your mock: the same
cases prove the mock behaves like the API, which makes your offline tests trustworthy.

## Example

`examples/api-quote/`: 4,117 cases, exact status/headers/body. The clean replica passed all, and a
banker's-rounding bug in VAT was caught in 149 of 4,117 mixed cases.
