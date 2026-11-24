"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import { ReplyView } from "@/components/chat/ReplyView";
import { problemText, send } from "@/lib/chat-client";
import { type GuidedAction, GuidedResponse } from "@/lib/contracts";

const STEPS = ["place", "party", "budget", "craving", "restriction"];
const round = (degrees: number) => Math.round(degrees * 1000) / 1000; // about 110 m

export function GuidedChat({ widget }: { widget: React.RefObject<HTMLDivElement | null> }) {
  const [now, setNow] = useState<GuidedResponse | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    heading.current?.focus();
  }, [now]);

  async function step(action?: GuidedAction) {
    if (busy || !widget.current) return;
    setBusy(true);
    setProblem("");
    try {
      const body = action && now ? { state: now.state, action } : {};
      setNow(await send(GuidedResponse, "/api/chat/guided", body, widget.current));
      setText("");
    } catch (error) {
      setProblem(problemText(error));
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void step({ type: "answer", text: text.trim() });
  }

  function locate() {
    if (!navigator.geolocation) return setProblem("อุปกรณ์นี้ไม่รองรับตำแหน่ง เลือกจังหวัดแทนได้");
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => void step({ type: "answer", near: { lat: round(coords.latitude), lon: round(coords.longitude) } }),
      () => setProblem("ไม่ได้รับตำแหน่ง เลือกจังหวัดแทนได้"),
      { timeout: 10_000, maximumAge: 300_000 },
    );
  }

  const alert = problem || now?.state.error;
  if (!now)
    return (
      <div className="chat">
        <p>ตอบ 5 ข้อสั้น ๆ แล้วรับรายชื่อร้าน โหมดนี้ไม่ใช้ AI จึงใช้ได้เสมอ</p>
        {alert && <p className="notice problem" role="alert">{alert}</p>}
        <p><button type="button" className="button primary" disabled={busy} onClick={() => void step()}>เริ่ม</button></p>
      </div>
    );
  const back = <button type="button" className="button" disabled={busy || now.state.step === "place"} onClick={() => void step({ type: "back" })}>ย้อนกลับ</button>;
  if (now.reply)
    return (
      <div className="chat">
        <h2 ref={heading} tabIndex={-1}>ร้านที่แนะนำ</h2>
        <ReplyView reply={now.reply} />
        {alert && <p className="notice problem" role="alert">{alert}</p>}
        <div className="actions">
          {back}
          <button type="button" className="button" disabled={busy} onClick={() => setNow(null)}>เริ่มใหม่</button>
        </div>
      </div>
    );
  return (
    <div className="chat">
      <p className="muted num">ข้อ {STEPS.indexOf(now.state.step) + 1} จาก {STEPS.length}</p>
      <h2 ref={heading} tabIndex={-1}>{now.prompt?.text}</h2>
      {alert && <p className="notice problem" role="alert">{alert}</p>}
      <div className="options" role="group" aria-label="ตัวเลือก">
        {now.prompt?.options.map((option) => (
          <button key={option} type="button" className="chip" disabled={busy} onClick={() => void step({ type: "answer", text: option })}>{option}</button>
        ))}
        {now.state.step === "place" && <button type="button" className="chip" disabled={busy} onClick={locate}>ใช้ตำแหน่งของฉัน</button>}
      </div>
      <form className="ask" onSubmit={submit}>
        <label>
          <span className="visually-hidden">คำตอบของคุณ</span>
          <input className="field" value={text} onChange={(e) => setText(e.target.value)} maxLength={100} autoComplete="off" placeholder="หรือพิมพ์คำตอบ" />
        </label>
        <button className="button primary" type="submit" disabled={busy}>ตอบ</button>
      </form>
      <div className="actions">
        {back}
        <button type="button" className="button" disabled={busy} onClick={() => void step({ type: "skip" })}>ข้าม</button>
      </div>
    </div>
  );
}
