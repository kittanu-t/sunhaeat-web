import type { PlaceDetail } from "@/lib/contracts";

export function DataNote({ place }: { place: PlaceDetail }) {
  if (place.is_demo) return <p className="muted">ร้านนี้แต่งขึ้นเพื่อแสดงหน้าเพจที่มีข้อมูลครบ ไม่มีอยู่จริง</p>;
  const sources = place.sources.map((s) => `${s.dataset} (${s.license})`).join(", ");
  return (
    <p className="muted">
      ข้อมูลจาก Overture Maps รุ่น {place.dataset_release}: {sources} ข้อมูลอาจไม่ตรงปัจจุบัน และยังไม่ยืนยันว่าร้านยังให้บริการ
    </p>
  );
}
