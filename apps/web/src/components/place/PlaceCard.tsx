import Link from "next/link";
import { PlateArt } from "@/components/place/PlateArt";
import type { Place } from "@/lib/contracts";
import { DEMO_LABEL, distanceText, priceText, tagText, whereText } from "@/lib/labels";

export function DemoBadge() {
  return <span className="badge">{DEMO_LABEL}</span>;
}

export function PlaceCard({ place, linkId }: { place: Place; linkId?: string }) {
  return (
    <article className="card" data-place={place.slug} data-demo={place.is_demo}>
      <PlateArt tags={place.tags} />
      <div>
        {place.is_demo && <DemoBadge />}
        <h3><Link id={linkId} href={`/r/${encodeURIComponent(place.slug)}`}>{place.name}</Link></h3>
        <p>{[distanceText(place.distance_m), whereText(place)].filter(Boolean).join(" · ")}</p>
        <p>{[tagText(place.tags) || "ยังไม่ระบุประเภท", priceText(place) ?? "ไม่ทราบราคา"].join(" · ")}</p>
      </div>
    </article>
  );
}
