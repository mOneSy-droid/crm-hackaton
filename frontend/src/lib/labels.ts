import type { IndustryBrief, Industry, ReviewStatus } from "./api";

/** Backend enum qiymatlarini foydalanuvchiga ko'rsatiladigan matnga aylantiradi. */
export const REVIEW_STATUS_LABEL: Record<ReviewStatus, string> = {
  pending: "Kutilmoqda",
  approved: "Tasdiqlangan",
  rejected: "Rad etilgan",
};

export function reviewStatusLabel(status: ReviewStatus): string {
  return REVIEW_STATUS_LABEL[status] ?? status;
}

/**
 * Interfeys tili. Hozircha o'zbekcha — ru/en qo'shilganda shu yerni
 * o'zgartirish yetarli, chunki barcha yorliqlar shu funksiyadan o'tadi.
 */
export const UI_LANG: "uz" | "ru" | "en" = "uz";

/**
 * `name_uz` / `name_ru` / `name_en` orasidan joriy tilga mosini oladi.
 *
 * Interfeyslarda indeks imzosi bo'lmagani uchun `object` qabul qilinadi va
 * ichkarida bir marta kastlanadi — chaqiruvchi tomonda kast kerak emas.
 */
export function localized(item: object | null | undefined, field: string): string {
  if (!item) return "";
  const record = item as Record<string, unknown>;
  return String(record[`${field}_${UI_LANG}`] ?? record[`${field}_uz`] ?? "");
}

/** Sohaga xos savol matni. */
export function fieldLabel(label: Record<string, string>): string {
  return label[UI_LANG] ?? label["uz"] ?? "";
}

/** "Taom" / "Mahsulot" / "Xizmat" — bitta katalog yozuvi. */
export function itemLabel(industry: IndustryBrief | Industry | null | undefined): string {
  return localized(industry, "item_label") || "Element";
}

/** "Menyu" / "Katalog" / "Xizmatlar" — katalogning o'zi. */
export function catalogLabel(industry: IndustryBrief | Industry | null | undefined): string {
  return localized(industry, "catalog_label") || "Katalog";
}

/** "Restoranlar" / "Do'konlar" — sohaning nomi. */
export function industryName(industry: IndustryBrief | Industry | null | undefined): string {
  return localized(industry, "name");
}
