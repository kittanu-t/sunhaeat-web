"use client";

import { type FormEvent, useState } from "react";
import { ReplyView } from "@/components/chat/ReplyView";
import { problemText, send } from "@/lib/chat-client";
import { ChatReply } from "@/lib/contracts";

interface Turn { text: string; reply: ChatReply }
const EXAMPLES = ["ส้มตำขอนแก่น งบ 100", "คาเฟ่โคราช", "อยากกินอะไรร้อน ๆ แถวอุบล"];

export function FreeChat({ widget }: { widget: React.RefObject<HTMLDivElement | null> }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  async function ask(message: string) {
    if (!message || busy || !widget.current) return;
    setBusy(true);
    setProblem("");
    try {
      const history = turns.slice(-6).map((t) => t.text);
      const reply = await send(ChatReply, "/api/chat/free", { text: message, history }, widget.current);
      setTurns((all) => [...all, { text: message, reply }]);
      setText("");
    } catch (error) {
      setText(message);
      setProblem(problemText(error));
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void ask(text.trim());
  }

  return (
    <div className="chat">
      <p className="notice">
        ถ้ากฎอ่านคำถามไม่ออก ข้อความจะส่งไป Gemini API ระดับฟรี ซึ่ง Google อาจนำไปปรับปรุงผลิตภัณฑ์ อย่าพิมพ์ข้อมูลส่วนตัว
      </p>
      {turns.length === 0 && (
        <div className="chips" role="group" aria-label="ตัวอย่างคำถาม">
          {EXAMPLES.map((e) => <button key={e} type="button" className="chip" disabled={busy} onClick={() => void ask(e)}>{e}</button>)}
        </div>
      )}
      <ol className="turns" aria-live="polite" aria-busy={busy}>
        {turns.map((turn, i) => (
          <li key={i}>
            <p className="mine">{turn.text}</p>
            <ReplyView reply={turn.reply} />
          </li>
        ))}
      </ol>
      {problem && <p className="notice problem" role="alert">{problem}</p>}
      <form className="ask" onSubmit={submit}>
        <label>
          <span className="visually-hidden">ข้อความของคุณ</span>
          <input className="field" value={text} onChange={(e) => setText(e.target.value)} maxLength={500} autoComplete="off"
            placeholder="อยากกินอะไร แถวไหน งบเท่าไร" />
        </label>
        <button className="button primary" type="submit" disabled={busy}>{busy ? "กำลังหา…" : "ส่ง"}</button>
      </form>
    </div>
  );
}
