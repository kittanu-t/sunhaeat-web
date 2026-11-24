# Threat model (R1)

Assets: API keys and secrets, the AI quota, catalog integrity, visitor privacy (messages, location, address), trust in what the site states. No accounts or payments exist in R1.

| Threat | Control | Where it is tested |
|---|---|---|
| Calling the API directly, forging or replaying identity | HMAC over time, method, path, session, IP hash and body; 60 s window; default deny | `test_auth.py`, `bff.test.ts` |
| Draining the AI quota | Turnstile, signed 24 h session, per-minute and per-day limits by session and IP, atomic global cap, `AI_ENABLED` kill switch | `test_quota.py`, `test_chat.py` |
| Prompt injection from users or place names | Model has no tools or write access; strict schemas; ID allowlist; rules win over model; replies are templates | `test_gemini.py`, `test_chat.py` |
| Catalog tampering | Runtime role is read-only on the catalog; row-level security everywhere; `anon`/`authenticated` have no access | `test_schema.py` |
| SQL injection | Bound parameters only; LIKE patterns escaped | `test_places.py` |
| XSS, clickjacking, unsafe links | React escaping, per-request nonce CSP, `frame-ancestors 'none'`, https-only links checked in pipeline, database and BFF | `proxy.test.ts`, `test_build.py`, Playwright CSP guard |
| CSRF | SameSite cookie, Origin must equal Host, Sec-Fetch-Site, JSON only | `bff.test.ts` |
| Leaking visitor data | Coordinates rounded and sent by POST; no message, coordinates, identity or provider text in logs; IPs stored only as keyed hashes | `test_chat.py`, `bff.test.ts`, `search.spec.ts` |
| Oversized or malformed input | 16 KB bodies, bounded fields, strict schemas, 3 s statement timeout | `test_auth.py`, `test_chat.py`, `bff.test.ts` |
| Misleading visitors | Unknown stays unknown; budget never confirmed without a price; fictional places labelled and kept apart | `test_places.py`, `place.spec.ts` |
| Leaked secrets in Git | gitleaks in CI over full history; env files ignored | CI |

## Accepted in R1

- A signed request can be replayed within 60 seconds by someone who can read server-to-server TLS traffic. Reads are idempotent and chat is quota-limited.
- IP limits affect people behind one shared address. IPv6 is grouped by /64.
- Public search endpoints have no per-visitor limit; the catalog is public data.
- Gemini's free tier may use submitted text to improve Google products. The page says so before the first message.
- Vercel's own request logs contain IP addresses and URLs; search words in `?q=` appear there.
