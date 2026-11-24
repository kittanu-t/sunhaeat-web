# Operations

Nothing below has been run against a cloud account yet.

## First deployment

1. **Supabase** (Singapore). Apply `supabase/migrations` in order as the owner. Then set a strong password: `alter role api_runtime login password '...'`. Do not add schema `app` to the exposed API schemas.
2. Check on the real project: `create extension` succeeded for `postgis` and `pg_trgm`; `select show_trgm('ส้มตำ')` is not empty (if empty, name search still works by substring but not by similarity); the anon key cannot read schema `app`.
3. **Import** from a trusted machine with `IMPORT_DATABASE_URL` set to the owner connection, then confirm the size is under 300 MB.
4. **Gemini**: read the model ID and limits in AI Studio. Set `GEMINI_MODEL`, and daily caps below the account limit. If the model spends output tokens on thinking, check that 512 tokens is enough; otherwise every answer falls back to rules with `ai_code: schema`.
5. **Vercel, project 1** root `apps/api`: `ENV=production`, `DATABASE_URL` (transaction pooler, user `api_runtime.<project-ref>`, `sslmode=require`), `API_HMAC_SECRET`, `CRON_SECRET`, `GEMINI_*`, `AI_ENABLED`. The daily cron sends `CRON_SECRET` as a bearer token.
6. **Vercel, project 2** root `apps/web`: `API_BASE_URL`, the same `API_HMAC_SECRET`, `SESSION_SECRET` (32+ characters), `TURNSTILE_SECRET_KEY`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`.
7. Secrets are entered in each dashboard by the owner, never in Git or chat.

## Smoke test

- `GET <api>/v1/places` without a signature is 401; `GET <api>/healthz` is 200; `/docs` is not served.
- Six quick chat messages: the sixth is refused. `AI_ENABLED=false`: both modes still answer.
- No secret appears in the browser bundle. Lighthouse mobile is at least 85. A phone in a private window goes from home to a recommendation without signing in.

## When something stops

| Sign | Cause and action |
|---|---|
| Home says search is not ready; demo pages still open | Supabase paused after 7 idle days or is down. Resume it in the dashboard, then open `/`. The daily cron normally prevents idling but free plans give no guarantee. |
| Database lost | Reapply migrations and re-import; the dataset is reproducible from `manifest.json`. There are no backups on the free plan and no user data in R1. |
| Chat says the AI quota is finished | Expected until 00:00 Bangkok. A single provider 429 also stops AI for that day. |
| Cost or abuse concern | Set `AI_ENABLED=false` and redeploy. |
| Secret exposed | Rotate it on both sides. `SESSION_SECRET` also invalidates guest sessions and IP hashes. |
