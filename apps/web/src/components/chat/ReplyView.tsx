import { PlaceCard } from "@/components/place/PlaceCard";
import type { ChatReply } from "@/lib/contracts";
import { DEMO_LABEL, PROVINCES, TAG_LABELS } from "@/lib/labels";

const FIRST = 5;
const WHY: Record<string, string> = {
  off: "ตอนนี้ AI ปิดอยู่",
  limit: "โควตา AI วันนี้หมดแล้ว",
  error: "AI ตอบไม่สำเร็จ",
};

function understood({ filters: f }: ChatReply): string[] {
  return [
    f.name && `ชื่อ: ${f.name}`,
    f.province_code && `จังหวัด: ${PROVINCES[f.province_code]}`,
    f.near && "ใกล้ตำแหน่งของคุณ",
    f.tags.length > 0 && `ประเภท: ${f.tags.map((t) => TAG_LABELS[t] ?? t).join(", ")}`,
    f.terms.length > 0 && `คำค้น: ${f.terms.join(", ")}`,
    f.budget_per_person && `งบต่อคน: ${f.budget_per_person} บาท`,
  ].filter((x): x is string => Boolean(x));
}

export function ReplyView({ reply }: { reply: ChatReply }) {
  const facts = understood(reply);
  const lanes = [
    ["ตรงเงื่อนไข", reply.result.matched], ["อาจตรง ไม่ทราบราคา", reply.result.maybe], [DEMO_LABEL, reply.result.demo],
  ] as const;
  return (
    <div className="reply">
      <p>{reply.text}</p>
      {facts.length > 0 && <p className="muted">ที่เข้าใจ: {facts.join(" · ")}</p>}
      {lanes.filter(([, places]) => places.length > 0).map(([name, places]) => (
        <section key={name} className="results" aria-label={name}>
          <h3 className={name === "ตรงเงื่อนไข" ? "good" : undefined}>{name}</h3>
          {places.slice(0, FIRST).map((p) => <PlaceCard key={p.slug} place={p} />)}
          {places.length > FIRST && (
            <details className="more">
              <summary>ดูอีก {places.length - FIRST} ร้าน</summary>
              <div className="results">{places.slice(FIRST).map((p) => <PlaceCard key={p.slug} place={p} />)}</div>
            </details>
          )}
        </section>
      ))}
      <p className="muted">
        {reply.mode === "ai" ? "AI ช่วยอ่านคำถามและเลือกลำดับ ข้อมูลร้านมาจากฐานข้อมูล" : "คำตอบนี้มาจากกฎ ไม่ได้ใช้ AI"}
        {reply.ai_unavailable && <> <span>{WHY[reply.ai_unavailable]}</span></>}
      </p>
      {lanes.some(([, places]) => places.length > 0) && <p className="muted">{reply.disclaimer}</p>}
    </div>
  );
}
