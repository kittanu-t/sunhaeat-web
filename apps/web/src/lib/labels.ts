import type { Place } from "@/lib/contracts";

export const PROVINCES: Record<string, string> = {
  "TH-30": "นครราชสีมา", "TH-31": "บุรีรัมย์", "TH-32": "สุรินทร์", "TH-33": "ศรีสะเกษ", "TH-34": "อุบลราชธานี", "TH-35": "ยโสธร",
  "TH-36": "ชัยภูมิ", "TH-37": "อำนาจเจริญ", "TH-38": "บึงกาฬ", "TH-39": "หนองบัวลำภู", "TH-40": "ขอนแก่น", "TH-41": "อุดรธานี",
  "TH-42": "เลย", "TH-43": "หนองคาย", "TH-44": "มหาสารคาม", "TH-45": "ร้อยเอ็ด", "TH-46": "กาฬสินธุ์", "TH-47": "สกลนคร",
  "TH-48": "นครพนม", "TH-49": "มุกดาหาร",
};

/** Same labels the API gives; used where a page must render without it. */
export const TAG_LABELS: Record<string, string> = {
  noodle: "ก๋วยเตี๋ยว/เส้น", isan: "อีสาน/ส้มตำ", hotpot_grill: "หมูกระทะ/ชาบู", coffee: "กาแฟ/คาเฟ่", bakery_dessert: "เบเกอรี่/ของหวาน",
  rice_made_to_order: "ข้าว/ตามสั่ง", congee: "โจ๊ก/ข้าวต้ม", seafood: "อาหารทะเล", japanese: "ญี่ปุ่น", korean: "เกาหลี",
  vietnamese: "เวียดนาม", chinese: "จีน", western: "ตะวันตก/สเต๊ก", fast_food: "ฟาสต์ฟู้ด/ไก่ทอด", bubble_tea: "ชานม",
};

export const WEEKDAYS = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์"];
export const DEMO_LABEL = "ร้านตัวอย่าง (สมมติ)";
export const UNKNOWN = "ยังไม่มีข้อมูล";

export function tagText(tags: string[]): string {
  return tags.map((t) => TAG_LABELS[t] ?? t).join(", ");
}

export function priceText(place: Pick<Place, "price_min" | "price_max">): string | null {
  if (place.price_max === null) return null;
  const low = place.price_min ?? place.price_max;
  return low === place.price_max ? `${low} บาท` : `${low}–${place.price_max} บาท`;
}

export function whereText(place: Pick<Place, "locality" | "province_name">): string {
  return place.locality && place.locality !== place.province_name ? `${place.locality}, ${place.province_name}` : place.province_name;
}

export function distanceText(metres: number | null): string | null {
  if (metres === null) return null;
  return metres < 1000 ? `${Math.max(10, Math.round(metres / 10) * 10)} ม.` : `${(metres / 1000).toFixed(1)} กม.`;
}
