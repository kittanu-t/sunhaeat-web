"use client";

import Link from "next/link";
import { useState } from "react";
import { type Bounds, PlaceMap } from "@/components/map/PlaceMap";
import { PlaceCard } from "@/components/place/PlaceCard";
import { type Place, PlaceList } from "@/lib/contracts";

interface Props {
  initial: Place[];
  q: string;
  tag: string;
  filtered: boolean;
  children: React.ReactNode;
}

const PROBLEM = "ค้นหาไม่สำเร็จ ลองอีกครั้งในอีกสักครู่";

async function load(request: Promise<Response>): Promise<Place[]> {
  const response = await request;
  if (!response.ok) throw new Error(String(response.status));
  return PlaceList.parse(await response.json()).places;
}

function currentPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("unsupported"));
    navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 10_000, maximumAge: 300_000 });
  });
}

const round = (degrees: number) => Math.round(degrees * 1000) / 1000; // about 110 m; exact position never leaves the page

export function SearchResults({ initial, q, tag, filtered, children }: Props) {
  const [places, setPlaces] = useState(initial);
  const [selected, setSelected] = useState<string | null>(null);
  const [area, setArea] = useState<Bounds | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  async function update(work: () => Promise<Place[]>, done: (n: number) => string) {
    setBusy(true);
    setStatus("กำลังค้นหา…");
    try {
      const found = await work();
      setPlaces(found);
      setSelected(null);
      setArea(null);
      setStatus(done(found.length));
    } catch (error) {
      setStatus(error instanceof Error && error.message === "location" ? "ไม่ได้รับตำแหน่ง เลือกจังหวัดหรือพิมพ์ค้นหาแทนได้" : PROBLEM);
    } finally {
      setBusy(false);
    }
  }

  const near = () => update(async () => {
    const position = await currentPosition().catch(() => { throw new Error("location"); });
    const body = JSON.stringify({
      lat: round(position.coords.latitude), lon: round(position.coords.longitude), ...(q ? { q } : {}), ...(tag ? { tags: [tag] } : {}),
    });
    return load(fetch("/api/near", { method: "POST", headers: { "content-type": "application/json" }, body }));
  }, (n) => `พบ ${n} ร้านในระยะ 5 กม. จากตำแหน่งโดยประมาณของคุณ`);

  const here = (bounds: Bounds) => update(() => {
    const query = new URLSearchParams({ bbox: bounds.map((n) => n.toFixed(4)).join(","), limit: "100" });
    if (q) query.set("q", q);
    if (tag) query.set("tag", tag);
    return load(fetch(`/api/places?${query}`));
  }, (n) => `พบ ${n} ร้านในบริเวณที่เห็นบนแผนที่`);

  function choose(slug: string) {
    setSelected(slug);
    const link = document.getElementById(`card-${slug}`);
    link?.scrollIntoView({ block: "center" });
    link?.focus({ preventScroll: true });
  }

  return (
    <>
      <PlaceMap places={places} selected={selected} onSelect={choose} onMove={setArea} label="แผนที่ร้านอาหาร">
        {area && <button type="button" className="button over" disabled={busy} onClick={() => here(area)}>ค้นหาในบริเวณนี้</button>}
      </PlaceMap>
      <div className="panel">
        <section className="results" aria-label="ผลการค้นหา" aria-busy={busy}>
          <div className="row">
            <h2>{filtered ? "ร้านที่ตรงกับที่ค้นหา" : "เริ่มจากร้านอาหารอีสาน"}</h2>
            <button type="button" className="button" disabled={busy} onClick={near}>ใกล้ฉัน</button>
          </div>
          <p role="status" className="muted">{status || `แสดง ${places.length} ร้าน`}</p>
          {places.map((p) => <PlaceCard key={p.slug} place={p} linkId={`card-${p.slug}`} />)}
          {places.length === 0 && (
            <div className="notice">
              <p>ยังไม่พบร้าน ลองคำสั้นลง เปลี่ยนจังหวัด หรือเลือกประเภทอาหาร</p>
              <Link href="/">ล้างตัวกรอง</Link>
            </div>
          )}
        </section>
        {children}
      </div>
    </>
  );
}
