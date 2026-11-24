import Link from "next/link";
import { PlaceCard } from "@/components/place/PlaceCard";
import { SearchResults } from "@/components/search/SearchResults";
import type { Place } from "@/lib/contracts";
import { PROVINCES, TAG_LABELS } from "@/lib/labels";
import { DEMO_PLACES, findPlaces, getMeta } from "@/lib/places";

type Search = Record<string, string | string[] | undefined>;
const one = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value) ?? "";

function href(filters: Record<string, string>): string {
  const query = new URLSearchParams(Object.entries(filters).filter(([, v]) => v));
  return query.size ? `/?${query}` : "/";
}

function DemoStrip({ places }: { places: Place[] }) {
  return (
    <section className="results" aria-label="ร้านตัวอย่าง">
      <h2>ดูเพจที่ข้อมูลครบ</h2>
      <p className="muted">ร้านจริงในชุดข้อมูลเปิดไม่มีราคาและเมนู ร้านสมมติเหล่านี้แสดงหน้าตาเมื่อเจ้าของกรอกข้อมูลครบ</p>
      {places.map((p) => <PlaceCard key={p.slug} place={p} />)}
    </section>
  );
}

export default async function Home({ searchParams }: { searchParams: Promise<Search> }) {
  const search = await searchParams;
  const q = one(search.q).trim().slice(0, 100);
  const province = one(search.province) in PROVINCES ? one(search.province) : "";
  const tag = one(search.tag) in TAG_LABELS ? one(search.tag) : "";
  const filtered = Boolean(q || province || tag);
  const query = new URLSearchParams({ limit: filtered ? "60" : "30" });
  // Unfiltered, the highest-confidence rows are global chains; start from local food instead.
  for (const [name, value] of Object.entries({ q, province, tag: filtered ? tag : "isan" })) if (value) query.set(name, value);

  const [meta, places] = await Promise.all([getMeta(), findPlaces(query)]);
  const demo = DEMO_PLACES.slice(0, 3);

  return (
    <div className="search">
      <div className="panel">
        <h1>วันนี้กินอะไรดีในอีสาน</h1>
        <form action="/" role="search">
          <label className="wide">
            <span className="visually-hidden">ชื่อร้านหรือเมนู</span>
            <input className="field" type="search" name="q" defaultValue={q} maxLength={100} placeholder="ชื่อร้าน หรือเมนู เช่น ส้มตำ" />
          </label>
          <label>
            <span className="visually-hidden">จังหวัด</span>
            <select className="field" name="province" defaultValue={province}>
              <option value="">ทุกจังหวัด</option>
              {Object.entries(PROVINCES).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
            </select>
          </label>
          {tag && <input type="hidden" name="tag" value={tag} />}
          <button className="button primary" type="submit">ค้นหา</button>
        </form>
        <nav className="chips" aria-label="ประเภทอาหาร" tabIndex={0}>
          {Object.entries(TAG_LABELS).map(([key, label]) => (
            <Link key={key} className="chip" prefetch={false} aria-current={key === tag ? "true" : undefined}
              href={href({ q, province, tag: key === tag ? "" : key })}>{label}</Link>
          ))}
        </nav>
        {meta && <p className="muted num">{meta.total.toLocaleString("th-TH")} ร้านจากข้อมูลเปิด ยังไม่ยืนยันว่าร้านเปิดอยู่จริง</p>}
        {!places && (
          <>
            <div className="notice problem" role="alert">
              <p><strong>ระบบค้นหายังไม่พร้อม</strong> ฐานข้อมูลอาจพักอยู่ ลองใหม่ในอีกไม่กี่นาที ระหว่างนี้ยังเปิดดูร้านตัวอย่างได้</p>
            </div>
            <DemoStrip places={demo} />
          </>
        )}
      </div>
      {places && (
        <SearchResults key={query.toString()} initial={places} q={q} tag={tag} filtered={filtered}>
          <DemoStrip places={demo} />
        </SearchResults>
      )}
    </div>
  );
}
