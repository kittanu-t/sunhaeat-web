"use client";

import { useRef, useState } from "react";
import { FreeChat } from "@/components/chat/FreeChat";
import { GuidedChat } from "@/components/chat/GuidedChat";

const MODES = [["free", "คุยอิสระ"], ["guided", "ตอบทีละข้อ"]] as const;

export function ChatApp() {
  const [mode, setMode] = useState<"free" | "guided">("free");
  const widget = useRef<HTMLDivElement>(null);

  function arrows(event: React.KeyboardEvent) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    const next = mode === "free" ? "guided" : "free";
    setMode(next);
    document.getElementById(`tab-${next}`)?.focus();
  }

  return (
    <>
      <div className="tabs" role="tablist" aria-label="โหมดคุย" onKeyDown={arrows}>
        {MODES.map(([key, label]) => (
          <button key={key} id={`tab-${key}`} type="button" role="tab" className="tab" aria-selected={mode === key} aria-controls={`panel-${key}`}
            tabIndex={mode === key ? 0 : -1} onClick={() => setMode(key)}>{label}</button>
        ))}
      </div>
      {/* Both stay mounted so switching modes keeps each conversation. */}
      <div id="panel-free" role="tabpanel" aria-labelledby="tab-free" hidden={mode !== "free"}><FreeChat widget={widget} /></div>
      <div id="panel-guided" role="tabpanel" aria-labelledby="tab-guided" hidden={mode !== "guided"}><GuidedChat widget={widget} /></div>
      <div ref={widget} />
    </>
  );
}
