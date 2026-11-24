import Link from "next/link";

export default function NotFound() {
  return (
    <div className="prose">
      <h1>ไม่พบหน้านี้</h1>
      <p>ร้านอาจถูกนำออกจากชุดข้อมูลแล้ว หรือลิงก์ไม่ถูกต้อง</p>
      <p><Link className="button" href="/">กลับไปค้นหา</Link></p>
    </div>
  );
}
