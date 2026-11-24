import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PlaceMap } from "@/components/map/PlaceMap";
import { DataNote } from "@/components/place/DataNote";
import { DemoBadge, PlaceCard } from "@/components/place/PlaceCard";
import { PlateArt } from "@/components/place/PlateArt";
import type { PlaceDetail } from "@/lib/contracts";
import { priceText, tagText, UNKNOWN, WEEKDAYS, whereText } from "@/lib/labels";
import { getNearby, getPlace } from "@/lib/places";

type Props = { params: Promise<{ slug: string }> };
const REPO = process.env.NEXT_PUBLIC_REPO_URL || "https://github.com/kittanu-t/sunhaeat-web";

function decoded(slug: string): string {
  try {
    return decodeURIComponent(slug);
  } catch {
    notFound();
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const place = await getPlace(decoded((await params).slug));
  return { title: place?.name ?? "ร้านอาหาร", robots: place?.is_demo ? { index: false } : undefined };
}

function Unknown() {
  return <span className="unknown">{UNKNOWN}</span>;
}

function reportUrl(place: PlaceDetail): string {
  const query = new URLSearchParams({ title: `ข้อมูลผิด: ${place.name}`, body: `ร้าน: ${place.slug}\n\nข้อมูลที่ถูกต้อง (โปรดอย่าใส่ข้อมูลส่วนตัว):\n` });
  return `${REPO}/issues/new?${query}`;
}

export default async function PlacePage({ params }: Props) {
  const slug = decoded((await params).slug);
  const place = await getPlace(slug);
  if (place === undefined) notFound();
  if (place === null)
    return (
      <div className="prose">
        <h1>เปิดเพจร้านไม่ได้ชั่วคราว</h1>
        <p role="alert">ฐานข้อมูลอาจพักอยู่ ลองใหม่ในอีกไม่กี่นาที</p>
      </div>
    );
  const nearby = place.is_demo ? [] : await getNearby(slug); // a fictional place has no real neighbours
  const maps = `https://www.google.com/maps/search/?api=1&query=${place.lat},${place.lon}`;
  return (
    <div className="place">
      <header>
        <PlateArt tags={place.tags} />
        <div>
          {place.is_demo && <DemoBadge />}
          <h1>{place.name}</h1>
          <p className="muted">{whereText(place)} · ภาพวาดตามประเภทอาหาร ไม่ใช่ภาพร้าน</p>
          {place.description && <p>{place.description}</p>}
        </div>
      </header>
      <dl className="facts">
        <div><dt>ประเภท</dt><dd>{tagText(place.tags) || <Unknown />}</dd></div>
        <div><dt>ราคา</dt><dd className="num">{priceText(place) ?? <Unknown />}</dd></div>
        <div>
          <dt>เวลาเปิด</dt>
          <dd className="num">
            {place.hours.length ? (
              <ul>{place.hours.map((h) => <li key={h.weekday}><span>{WEEKDAYS[h.weekday]}</span><span>{h.opens}–{h.closes}</span></li>)}</ul>
            ) : <Unknown />}
          </dd>
        </div>
        <div>
          <dt>เมนู</dt>
          <dd className="num">
            {place.menu.length ? (
              <ul>{place.menu.map((m) => <li key={m.name}><span>{m.name}</span><span>{m.price_thb === null ? UNKNOWN : `${m.price_thb} บาท`}</span></li>)}</ul>
            ) : <Unknown />}
          </dd>
        </div>
        <div><dt>ที่อยู่</dt><dd>{place.address || <Unknown />}</dd></div>
      </dl>
      <PlaceMap places={[place]} label={`แผนที่ ${place.name}`} />
      <div className="actions full">
        {!place.is_demo && <a className="button primary" href={maps} target="_blank" rel="noopener noreferrer">เปิดใน Google Maps</a>}
        {place.facebook_url && <a className="button" href={place.facebook_url} target="_blank" rel="noopener noreferrer nofollow">Facebook</a>}
        {place.website && <a className="button" href={place.website} target="_blank" rel="noopener noreferrer nofollow">เว็บไซต์</a>}
        <a className="button" href={reportUrl(place)} target="_blank" rel="noopener noreferrer">แจ้งข้อมูลผิด</a>
      </div>
      <div className="full"><DataNote place={place} /></div>
      {nearby.length > 0 && (
        <section className="full results" aria-label="ร้านใกล้เคียง">
          <h2>ร้านใกล้เคียง</h2>
          {nearby.map((p) => <PlaceCard key={p.slug} place={p} />)}
        </section>
      )}
    </div>
  );
}
