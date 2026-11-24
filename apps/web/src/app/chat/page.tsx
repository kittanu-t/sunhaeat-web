import type { Metadata } from "next";
import { ChatApp } from "@/components/chat/ChatApp";

export const metadata: Metadata = { title: "คุยกับ AI" };

export default function ChatPage() {
  return (
    <div className="talk">
      <h1>ให้ช่วยเลือกร้าน</h1>
      <ChatApp />
    </div>
  );
}
