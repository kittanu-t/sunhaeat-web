# SunHaEat Web: แผน portfolio project

## Context
สร้าง web app ใหม่จากแนวคิด SunHaEat เพื่อใส่ resume สาย NLP/AI เน้นเดโมจริง ใช้ฟรี ไม่เน้นรองรับคนจำนวนมาก ผู้ใช้คุมงาน ส่วน Claude เขียน

**ตัดสินใจแล้ว (โดยผู้ใช้):** repo ใหม่ `sunhaeat-web` (public, ประวัติใหม่) · ภาคอีสาน · Next.js บน Vercel + FastAPI + Supabase · Gemini free · guest ใช้ AI ได้แบบจำกัดโควตา · R1 ภายใน 1 สัปดาห์: ข้อมูลจริง แผนที่ เพจ AI 2 โหมด · R2: เจ้าของร้าน รีวิว

**ข้อเสนอของ Claude (แก้ได้):** ทุกข้อด้านล่างที่ไม่อยู่ในรายการข้างบน

**ไม่ทำ:** ฟีด/ติดตาม/คอมเมนต์/แชตระหว่างผู้ใช้, สั่งอาหาร, จ่ายเงิน, scraping Wongnai/Google/Grab, mobile app, LINE

## Approaches
| แบบ | ข้อดี / ข้อเสีย |
|---|---|
| **Next.js + FastAPI + Supabase (เลือก)** | โชว์ Python AI/eval + PostGIS/RLS; deploy 2 ส่วน |
| Next.js + Supabase | ง่ายกว่า; โชว์ Python น้อย |
| Next.js + Workers + D1 | reuse มากสุด; ไม่มี PostGIS/RLS |

## ข้อมูล
- หลัก: Overture Places (Foursquare และแหล่งอื่น) ดาวน์โหลดด้วย DuckDB แล้ว import; เก็บ `source`, `source_id`, `release`, `license`, `confidence` รายร้าน พร้อมหน้า attribution
- ใช้ `taxonomy`/`basic_category` เพราะ [`categories` ถูกถอดแล้ว](https://docs.overturemaps.org/guides/places); กรอง `operating_status`, confidence, ตัดซ้ำด้วยชื่อ+ระยะ แล้ว clip ขอบเขต 20 จังหวัด
- ไม่ใช้ Google Places เป็น DB ([ห้ามเก็บถาวร](https://developers.google.com/maps/documentation/places/web-service/policies?authuser=6)); มีแค่ลิงก์ออกไป Google Maps
- ไม่นำ catalog 102 ร้านเดิมมา: provenance ไม่ยืนยันและเป็น private
- **ความเสี่ยงใหญ่สุด:** คาดว่าชุดนี้ไม่มีราคา เมนู รีวิว เวลาเปิด → ค่าที่ไม่ทราบคงเป็น unknown; ผลลัพธ์แยก “ตรงเงื่อนไข” กับ “อาจตรง แต่ไม่ทราบราคา” และมีร้าน **demo สมมติ ~12 ร้าน ติดป้ายชัด** ให้เห็นเพจครบทุกช่อง; ร้าน demo ไม่ถูกนับเป็นข้อมูลจริงหรือปนใน eval ข้อมูลจริง
- **Gate วันแรก:** spike นับร้านต่อจังหวัด, % มีเบอร์/ที่อยู่/เว็บ, สุ่มตรวจ 50 ร้าน ถ้าร้านใช้ได้ <2,000 หรือสุ่มผ่าน <80% หยุดมาปรึกษา (ลองเสริม OSM ซึ่งเป็น ODbL ต้องแยก license)

## สถาปัตยกรรม
```
Browser → Next.js (Vercel) → FastAPI (Vercel Python, project แยก) → Supabase Postgres
   └ MapLibre + OpenFreeMap tiles              └ Gemini (มี rules fallback)
```
- Monorepo: `apps/web`, `apps/api`, `pipeline/`, `supabase/migrations`, `eval/`, `docs/`
- FastAPI บน [Vercel Python](https://vercel.com/docs/functions/runtimes/python) รองรับ streaming; ไม่ลง torch/PyThaiNLP ใน API
- Browser เรียกเฉพาะ Next route handlers; Next ลงนาม HMAC+timestamp ไป FastAPI จึงไม่เปิด CORS
- PostGIS สำหรับ “ใกล้ฉัน”/viewport, `pg_trgm` สำหรับชื่อไทย; ตรวจ extensions บนบัญชีจริง
- `pgvector` เลื่อนไป R3 เพราะข้อมูล POI แทบไม่มีข้อความให้ embed; เปิดใช้เมื่อมีรีวิว/คำอธิบายและ eval ชนะ baseline (ต่างจาก preview ที่เลือก จึงขอให้ยืนยัน)
- ตารางหลัก: `restaurants`, `restaurant_sources`, `menu_items`, `opening_hours`, `provinces`, `ai_usage`, `rate_limits`; R2 เพิ่ม `profiles`, `claims`, `reviews`, `saves`, `posts`, `audit_log`

## หน้าเว็บ (R1)
- `/` ค้นหา + แผนที่ + รายการ (bottom sheet บนมือถือ), filter จังหวัด/ประเภท/ระยะ, URL แชร์ได้
- `/r/[slug]` เพจร้าน: ปก ข้อมูล แผนที่ เมนู ร้านใกล้เคียง ที่มา/วันที่ข้อมูล ปุ่มแจ้งข้อมูลผิด
- `/chat` 2 โหมด, `/about` สถาปัตยกรรม ผล eval ข้อจำกัด
- ไทยเป็นหลัก; ทำ design direction ก่อนลง UI

## AI chat
1. **คุยอิสระ:** ข้อความ + history สั้น → Gemini structured output เป็น `Filters` → SQL → เลือก ID จาก candidates → ตอบเป็นการ์ดจาก DB
2. **ถามทีละข้อ:** state machine: ที่ไหน → กี่คน → งบต่อคน → อยากกินอะไร → ข้อจำกัด; กดปุ่มหรือพิมพ์ ข้ามได้ ย้อนได้; LLM ใช้เฉพาะคำตอบพิมพ์อิสระ จึงทำงานได้แม้ LLM ล่ม
- “กี่คน” ใช้คำนวณงบรวม ไม่อ้างว่าร้านมีที่นั่งพอ; ตำแหน่งใช้เมื่อกดอนุญาต ปัดพิกัดก่อนใช้ และไม่บันทึก
- ย้ายหลักการเดิมเป็น Python: parser (`src/search/parse.ts`), เวลา (`src/search/hours.ts`), ranking (`src/search/search.ts`), validation/timeout (`src/providers/kku.ts`), hard constraints ที่โมเดลผ่อนไม่ได้ (`src/providers/fallback.ts`), จองโควตา atomic (`src/data/repository.ts`)
- **Eval:** 120 คำถามไทยที่ตรวจมือ (slot extraction, retrieval, งดตอบ, injection) แยก dev/test; เทียบ rules vs Gemini; รายงาน slot F1 (ระบุ micro/macro), Recall@k, constraint violation, latency, tokens พร้อม commit/model/dataset hash

## Security
ของเดิมมี signature, dedup, rate limit, admin allowlist อยู่แล้ว สิ่งที่ทำใหม่สำหรับเว็บ:
- Threat model + `SECURITY.md`; RLS ทุกตาราง default deny; explicit grants; API ใช้ DB role สิทธิ์จำกัด ห้าม service role ใน runtime
- Guest: Turnstile + signed session + จำกัดต่อ session/IP hash + เพดานรวมต่อวัน; ขนาด input, timeout, kill switch
- CSP nonce, HSTS, ตรวจ Origin, Zod/Pydantic, parameterized SQL, React escaping, อนุญาตเฉพาะ URL https
- Prompt injection: LLM ไม่มี tools/สิทธิ์เขียน, schema เคร่ง, ID allowlist, ไม่ส่งตัวตน; แจ้งผู้ใช้ว่า [free tier อาจใช้ข้อมูลปรับปรุงผลิตภัณฑ์](https://ai.google.dev/gemini-api/docs/pricing)
- CI: lint, tests, gitleaks, dependency audit, CodeQL; logs ไม่มีข้อความแชตหรือ IP ดิบ
- R2: Supabase Auth, claim ต้อง admin อนุมัติ, รูปตรวจ MIME/ขนาดและ re-encode, tests ข้ามผู้ใช้ (IDOR)

## ลำดับงาน
**R1** (เป้า 1 สัปดาห์; 3–4 วันเป็นไปได้ถ้าข้อมูลและบัญชีพร้อม)
1. Data spike + gate; ตรวจ Gemini limits
2. Repo, schema/RLS, import, CI
3. API ค้นหา + แผนที่ + เพจร้าน
4. AI 2 โหมด + quota + fallback
5. Security tests, eval, Playwright, deploy preview → production, README + ภาพ/GIF

**R2:** login, รีวิว/บันทึก, claim/แก้เพจ/โพสต์, admin moderation
**R3:** pgvector hybrid, ขยายประเทศ, EN

ถ้าเวลาไม่พอ ตัดตามลำดับ: ร้านใกล้เคียง → streaming → แชร์ filter; ไม่ตัด security, eval, attribution

## Free-tier risks
- [Supabase Free พักหลังไม่ใช้ 7 วัน, 500 MB, ไม่มี backup](https://supabase.com/pricing): cron รายวันล้าง rate limits/ตรวจสุขภาพ, migration+import สร้างใหม่ได้, และ snapshot ร้าน demo ให้หน้าเว็บไม่พังเมื่อ DB ล่ม
- Gemini limits เปลี่ยนได้: อ่านจากบัญชี ตั้งเพดานต่ำกว่า ไม่เปิด billing
- OpenFreeMap ไม่มี SLA: style URL เปลี่ยนผ่าน config

## ต้องใช้จากผู้ใช้
บัญชี/คีย์ Supabase, Gemini, Turnstile, เชื่อม Vercel โดยใส่ secrets เองใน dashboard; ตรวจ dataset eval; ขอ OK อีกครั้งก่อนสร้าง/push public repo, สร้าง cloud resources และ deploy

## เมื่ออนุมัติ
บันทึกแผนนี้เป็น design doc ใน `ChatGPT\sunhaeat-web` (git local), ใช้ writing-plans ทำแผน task แล้วเริ่มข้อ 1 โดยไม่แตะ repo เดิม

## Verification
- Pipeline: นับแถว/ขอบเขต/ซ้ำ, import ซ้ำได้ผลเดิม, DB <300 MB
- pytest + Postgres จริง (RLS, quota พร้อมกัน, unknown price), Vitest, Playwright desktop/มือถือ
- AI: mock ใน CI; live eval มีเพดาน; ปิด key แล้วทั้งสองโหมดยังตอบ; constraint violation = 0 บน test set
- Security: ยิงเกินโควตา, HMAC ผิด/เก่า, XSS ในชื่อร้าน, injection, anon write ต้องถูกปฏิเสธ
- Production: เปิดแบบ incognito บนมือถือ, Lighthouse mobile ≥85, HR ใช้จากหน้าแรกถึงคำแนะนำได้โดยไม่ login

## จุดขายใน resume (เติมตัวเลขหลังวัดจริง)
Data pipeline เปิด + geospatial search · grounded Thai LLM พร้อม eval · security-by-design และ graceful fallback บนงบ 0 บาท

## Amendments หลัง data gate (2026-11-24, รอผู้ใช้ยืนยันพร้อม task plan)
หลักฐาน: [data-gate](../../evidence/2026-11-24-data-gate.md)
- เกณฑ์กรองใช้ confidence ≥0.8 + ตัดชื่อธุรกิจอื่น; `operating_status` ใช้ได้เฉพาะตัดค่าที่ระบุว่าปิด
- ไม่นำเข้าเบอร์โทรใน R1; ตัดเบอร์ที่ฝังในชื่อ; ใช้ลิงก์ Facebook/เว็บแทน
- แท็กประเภทอาหารมาจากชื่อไทย + taxonomy โดยชื่อชนะ
- ร้านจริงไม่มีราคา/เวลา จึงอยู่กลุ่ม “อาจตรง” เสมอเมื่อระบุงบ; แสดงร้านตัวอย่างสมมติที่ตรงงบในแถบแยกที่ติดป้าย
