import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans_Thai_Looped, Pattaya } from "next/font/google";
import Link from "next/link";
import { connection } from "next/server";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

const body = IBM_Plex_Sans_Thai_Looped({ weight: ["400", "600"], subsets: ["thai", "latin"], variable: "--font-body" });
const sign = Pattaya({ weight: "400", subsets: ["thai", "latin"], variable: "--font-sign" });

export const metadata: Metadata = {
  title: { default: "SunHaEat หาร้านกินในอีสาน", template: "%s | SunHaEat" },
  description: "ค้นหาร้านอาหารใน 20 จังหวัดภาคอีสานจากข้อมูลเปิด พร้อมแผนที่และผู้ช่วยที่บอกตรง ๆ ว่าอะไรยังไม่รู้",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f6f9fc" };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  await connection(); // every page renders per request so it can carry its CSP nonce
  return (
    <html lang="th" className={`${body.variable} ${sign.variable}`}>
      <body>
        <a className="skip" href="#main">ข้ามไปเนื้อหา</a>
        <header className="site">
          <Link className="wordmark" href="/">SunHaEat</Link>
          <nav aria-label="หลัก">
            <Link href="/">ค้นหา</Link>
            <Link href="/chat">คุยกับ AI</Link>
            <Link href="/about">เกี่ยวกับ</Link>
          </nav>
        </header>
        <main id="main">{children}</main>
        <footer className="foot">
          ข้อมูลร้านจาก Overture Maps (Meta, AllThePlaces, Foursquare, Microsoft) ยังไม่ยืนยันว่าร้านเปิดอยู่จริง{" "}
          <Link href="/about">แหล่งข้อมูลและข้อจำกัด</Link>
        </footer>
      </body>
    </html>
  );
}
