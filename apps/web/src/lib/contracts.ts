import { z } from "zod";

const httpsUrl = z.string().max(500).refine((s) => s.startsWith("https://") && URL.canParse(s));
export const provinceCode = z.string().regex(/^TH-[34][0-9]$/);

export const Place = z.object({
  id: z.uuid(),
  slug: z.string().min(1).max(200),
  name: z.string().min(1).max(200),
  province_code: provinceCode,
  province_name: z.string(),
  lat: z.number(),
  lon: z.number(),
  address: z.string().nullable(),
  locality: z.string().nullable(),
  tags: z.array(z.string()),
  website: httpsUrl.nullable(),
  facebook_url: httpsUrl.nullable(),
  price_min: z.number().nullable(),
  price_max: z.number().nullable(),
  is_demo: z.boolean(),
  distance_m: z.number().nullable(),
});
export const PlaceDetail = Place.extend({
  description: z.string().nullable(),
  menu: z.array(z.object({ name: z.string(), price_thb: z.number().nullable() })),
  hours: z.array(z.object({ weekday: z.number().int().min(0).max(6), opens: z.string(), closes: z.string() })),
  sources: z.array(z.object({ dataset: z.string(), license: z.string() })),
  dataset_release: z.string(),
});
export const PlaceList = z.object({ places: z.array(Place) });
export const Meta = z.object({
  provinces: z.array(z.object({ code: provinceCode, name: z.string(), count: z.number() })),
  tags: z.array(z.object({ tag: z.string(), label: z.string() })),
  total: z.number(),
  release: z.string().nullable(),
});

const Near = z.strictObject({
  lat: z.number().min(-90).max(90),
  lon: z.number().min(-180).max(180),
  radius_m: z.number().int().min(100).max(50_000).optional(),
});
export const Filters = z.object({
  name: z.string().nullable(),
  province_code: provinceCode.nullable(),
  tags: z.array(z.string()),
  terms: z.array(z.string()),
  near: Near.nullable(),
  budget_per_person: z.number().nullable(),
  needs_clarification: z.boolean(),
});
export const SearchResult = z.object({ matched: z.array(Place), maybe: z.array(Place), demo: z.array(Place) });
export const ChatReply = z.object({
  mode: z.enum(["ai", "rules"]),
  text: z.string(),
  filters: Filters,
  result: SearchResult,
  disclaimer: z.string(),
  ai_unavailable: z.enum(["off", "limit", "error"]).nullable(),
});

const message = z.string().trim().min(1).max(500);
export const FreeRequest = z.strictObject({ text: message, history: z.array(message).max(6).default([]) });

export const GuidedState = z.strictObject({
  step: z.enum(["place", "party", "budget", "craving", "restriction", "done"]),
  answers: z.strictObject({
    place: z.union([provinceCode, Near]).nullable(),
    party: z.number().int().nullable(),
    budget: z.number().int().nullable(),
    craving: z.string().max(60).nullable(),
    restriction: z.string().max(60).nullable(),
  }).partial(),
  error: z.string().max(200).nullable().optional(),
});
export const GuidedAction = z.discriminatedUnion("type", [
  z.strictObject({ type: z.literal("answer"), text: z.string().max(100).optional(), near: Near.optional() }),
  z.strictObject({ type: z.literal("skip") }),
  z.strictObject({ type: z.literal("back") }),
]);
export const GuidedRequest = z.strictObject({ state: GuidedState.optional(), action: GuidedAction.optional() });
export const GuidedResponse = z.object({
  state: GuidedState,
  prompt: z.object({ text: z.string(), options: z.array(z.string()) }).nullable(),
  reply: ChatReply.nullable(),
});
export const SessionRequest = z.strictObject({ token: z.string().min(1).max(4096) });

export type Place = z.infer<typeof Place>;
export type PlaceDetail = z.infer<typeof PlaceDetail>;
export type Meta = z.infer<typeof Meta>;
export type SearchResult = z.infer<typeof SearchResult>;
export type ChatReply = z.infer<typeof ChatReply>;
export type GuidedState = z.infer<typeof GuidedState>;
export type GuidedAction = z.infer<typeof GuidedAction>;
export type GuidedResponse = z.infer<typeof GuidedResponse>;
