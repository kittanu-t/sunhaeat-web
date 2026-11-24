// An enamel plate with a drawing of the kind of food. Never a picture of the actual restaurant.
const RIM = "#1d3f9a";
const FOOD: Record<string, React.ReactNode> = {
  noodle: (
    <g fill="none" stroke="#e0a526" strokeWidth="3.5" strokeLinecap="round">
      <path d="M30 44c8-8 12 8 20 0s12 8 20 0" /><path d="M30 52c8-8 12 8 20 0s12 8 20 0" /><path d="M32 60c7-7 11 7 18 0s11 7 18 0" />
    </g>
  ),
  isan: (
    <g strokeLinecap="round" strokeWidth="3.5" fill="none">
      <path stroke="#7cab3a" d="M30 58 52 38M36 64l24-22M44 66l22-20" /><path stroke="#c22f1f" d="m34 44 14 14" />
      <circle cx="62" cy="62" r="4" fill="#c22f1f" stroke="none" /><circle cx="56" cy="38" r="3.5" fill="#c22f1f" stroke="none" />
    </g>
  ),
  hotpot_grill: (
    <g><path d="M32 60a18 14 0 0 1 36 0z" fill="#44526f" /><path d="M38 52h24M42 46h16" stroke="#b9532f" strokeWidth="5" strokeLinecap="round" /></g>
  ),
  coffee: (
    <g><circle cx="50" cy="50" r="17" fill="#fff" stroke={RIM} strokeWidth="2.5" /><circle cx="50" cy="50" r="12.5" fill="#6b4226" /><path d="M44 50c4-6 8 6 12 0" stroke="#e8cfae" strokeWidth="3" fill="none" strokeLinecap="round" /></g>
  ),
  bakery_dessert: (
    <g><path d="m32 62 8-24 28 10v14z" fill="#f3d9a4" stroke="#b9822f" strokeWidth="2.5" strokeLinejoin="round" /><circle cx="46" cy="40" r="5" fill="#c22f1f" /></g>
  ),
  rice_made_to_order: (
    <g><path d="M34 60a16 18 0 0 1 32 0z" fill="#fff" stroke="#c9d5ee" strokeWidth="2.5" /><path d="m58 62 10-8" stroke="#2f6b2a" strokeWidth="4" strokeLinecap="round" /><circle cx="38" cy="62" r="4" fill="#c22f1f" /></g>
  ),
  congee: (
    <g><circle cx="50" cy="50" r="18" fill="#fbf4df" stroke="#d9c48a" strokeWidth="2.5" /><circle cx="54" cy="48" r="6" fill="#f4c542" /><path d="M38 56h8M42 60h6" stroke="#2f6b2a" strokeWidth="3" strokeLinecap="round" /></g>
  ),
  seafood: (
    <g><path d="M30 50c10-14 26-14 34 0-8 14-24 14-34 0z" fill="#e57b4c" /><path d="m64 50 8-8v16z" fill="#e57b4c" /><circle cx="39" cy="48" r="2.5" fill="#14213d" /></g>
  ),
  japanese: (
    <g><rect x="32" y="50" width="16" height="12" rx="5" fill="#fff" stroke="#c9d5ee" strokeWidth="2" /><path d="M30 50c4-8 16-8 20 0z" fill="#e57b4c" /><circle cx="62" cy="54" r="9" fill="#24384a" /><circle cx="62" cy="54" r="5.5" fill="#fff" /><circle cx="62" cy="54" r="2" fill="#7cab3a" /></g>
  ),
  western: (
    <g><path d="M32 52c2-14 30-16 36-4 4 10-8 18-18 16-8-2-19 0-18-12z" fill="#8a4a2b" /><path d="m42 50 8-6m0 12 10-8" stroke="#5c2f19" strokeWidth="3" strokeLinecap="round" /></g>
  ),
  bubble_tea: (
    <g><path d="M38 36h24l-4 30H42z" fill="#d8b48a" stroke="#8a6238" strokeWidth="2.5" strokeLinejoin="round" /><path d="m54 36 6-10" stroke="#c22f1f" strokeWidth="4" strokeLinecap="round" /><circle cx="46" cy="60" r="3" fill="#14213d" /><circle cx="53" cy="61" r="3" fill="#14213d" /><circle cx="50" cy="54" r="3" fill="#14213d" /></g>
  ),
};
const SAME: Record<string, string> = { korean: "hotpot_grill", vietnamese: "noodle", chinese: "congee", fast_food: "western" };
const UTENSILS = (
  <g stroke="#44526f" strokeWidth="4" strokeLinecap="round" fill="none"><path d="M42 36v28M36 36v8c0 6 12 6 12 0v-8" /><path d="M60 64V36c6 4 6 14 0 16" /></g>
);

export function PlateArt({ tags }: { tags: string[] }) {
  const tag = tags.map((t) => SAME[t] ?? t).find((t) => t in FOOD);
  return (
    <svg className="plate" viewBox="0 0 100 100" aria-hidden="true">
      <circle cx="50" cy="50" r="47" fill="#fff" stroke={RIM} strokeWidth="4" />
      <circle cx="50" cy="50" r="33" fill="#f6f9fc" stroke="#c9d5ee" strokeWidth="1.5" />
      {tag ? FOOD[tag] : UTENSILS}
    </svg>
  );
}
