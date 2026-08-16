/**
 * Backend klienti. Barcha so'rovlar shu yerdan o'tadi.
 *
 * Tiplar backenddagi pydantic sxemalariga aynan mos — nomi o'zgarsa
 * TypeScript darhol ogohlantiradi.
 */

const RAW_API_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.["VITE_API_URL"]) ||
  "http://localhost:8000";

export const API_URL = String(RAW_API_URL).replace(/\/$/, "");
const PREFIX = "/api/v1";

const ACCESS_KEY = "crm.access_token";
const REFRESH_KEY = "crm.refresh_token";

// ---------------------------------------------------------------------------
// Tiplar
// ---------------------------------------------------------------------------

export type Language = "uz" | "ru" | "en";
export type UserRole = "admin" | "owner" | "customer";
export type ReviewStatus = "pending" | "approved" | "rejected";
export type BotStatus = "draft" | "pending" | "active" | "stopped" | "failed";

export interface Category {
  id: number;
  key: string;
  industry_id: number;
  name_uz: string;
  name_ru: string;
  name_en: string;
}

/** Sohaga xos qo'shimcha savol — forma shu tavsif asosida chiziladi. */
export interface IndustryField {
  key: string;
  type: "text" | "number" | "choice";
  label: Record<string, string>;
  choices: string[];
}

/**
 * Faoliyat sohasi. Yorliqlar shu yerdan olinadi: restoranga "Taom",
 * do'konga "Mahsulot" deb ko'rsatiladi — kodda shart yozilmaydi.
 */
export interface Industry {
  id: number;
  key: string;
  icon: string;
  name_uz: string;
  name_ru: string;
  name_en: string;
  entity_label_uz: string;
  entity_label_ru: string;
  entity_label_en: string;
  item_label_uz: string;
  item_label_ru: string;
  item_label_en: string;
  catalog_label_uz: string;
  catalog_label_ru: string;
  catalog_label_en: string;
  fields: IndustryField[];
  categories: Category[];
}

/** Biznes javobiga qo'shiladigan qisqartirilgan soha. */
export type IndustryBrief = Pick<
  Industry,
  | "id"
  | "key"
  | "icon"
  | "name_uz"
  | "name_ru"
  | "name_en"
  | "item_label_uz"
  | "item_label_ru"
  | "item_label_en"
  | "catalog_label_uz"
  | "catalog_label_ru"
  | "catalog_label_en"
>;

export interface Restaurant {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  work_hours: string | null;
  phone: string | null;
  logo_url: string | null;
  is_active: boolean;
  is_verified: boolean;
  rating_avg: number;
  rating_count: number;
  industry: IndustryBrief;
  category: Category | null;
  /** Sohaga xos qo'shimcha maydonlar, `Industry.fields` bo'yicha */
  attributes: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Review {
  id: number;
  restaurant_id: number;
  rating: number;
  text: string | null;
  status: ReviewStatus;
  owner_reply: string | null;
  owner_replied_at: string | null;
  photos: string[];
  author: { id: number | null; display_name: string } | null;
  created_at: string;
}

export interface MenuItem {
  id: number;
  restaurant_id: number;
  name: string;
  description: string | null;
  price: number | null;
  section: string | null;
  photo_url: string | null;
  is_available: boolean;
  sort_order: number;
}

export interface DashboardStats {
  restaurant_id: number;
  rating_avg: number;
  rating_count: number;
  reviews_pending: number;
  reviews_last_7_days: number;
  reviews_last_30_days: number;
  rating_breakdown: Record<string, number>;
  menu_items: number;
  bots_active: number;
}

export interface BotInstance {
  id: number;
  restaurant_id: number;
  bot_username: string | null;
  token_hint: string | null;
  status: BotStatus;
  status_detail: string | null;
  purpose: string | null;
  languages: string | null;
  features: string | null;
  tone: string | null;
  has_generated_config: boolean;
  started_at: string | null;
  created_at: string;
}

export interface Me {
  id: number;
  full_name: string | null;
  username: string | null;
  phone_masked: string | null;
  role: UserRole;
  language: Language;
  telegram_username: string | null;
  is_active: boolean;
  created_at: string;
  restaurant_ids: number[];
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface FieldProblem {
  field: string;
  message: string;
}

// ---------------------------------------------------------------------------
// Xatolar
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  problems: FieldProblem[];

  constructor(status: number, message: string, problems: FieldProblem[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.problems = problems;
  }

  /** Forma maydoni tagida ko'rsatish uchun. */
  problemFor(field: string): string | undefined {
    return this.problems.find((p) => p.field === field)?.message;
  }
}

// ---------------------------------------------------------------------------
// Token saqlash (SSR'da localStorage yo'q — hamma joyda tekshiramiz)
// ---------------------------------------------------------------------------

const hasWindow = () => typeof window !== "undefined";

export const tokens = {
  access: () => (hasWindow() ? localStorage.getItem(ACCESS_KEY) : null),
  refresh: () => (hasWindow() ? localStorage.getItem(REFRESH_KEY) : null),
  save(pair: TokenPair) {
    if (!hasWindow()) return;
    localStorage.setItem(ACCESS_KEY, pair.access_token);
    localStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clear() {
    if (!hasWindow()) return;
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
  isLoggedIn: () => Boolean(hasWindow() && localStorage.getItem(ACCESS_KEY)),
};

// ---------------------------------------------------------------------------
// So'rov yuborish
// ---------------------------------------------------------------------------

async function toApiError(response: Response): Promise<ApiError> {
  let detail = "Serverda kutilmagan xatolik";
  let problems: FieldProblem[] = [];
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") detail = data.detail;
    if (Array.isArray(data?.problems)) problems = data.problems;
  } catch {
    // JSON emas — standart matn qoladi
  }
  if (response.status === 0 || response.status >= 500) {
    detail = "Server javob bermayapti. Birozdan keyin urinib ko'ring.";
  }
  return new ApiError(response.status, detail, problems);
}

/** Refresh bir vaqtda bir marta ishlasin — parallel 401 lar bitta so'rovni kutadi. */
let refreshInFlight: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const refresh = tokens.refresh();
  if (!refresh) return false;

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_URL}${PREFIX}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!response.ok) {
          tokens.clear();
          return false;
        }
        tokens.save((await response.json()) as TokenPair);
        return true;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

interface RequestOptions {
  method?: string | undefined;
  body?: unknown;
  auth?: boolean | undefined;
  formData?: FormData | undefined;
  /** ichki: refresh'dan keyin bir marta qayta urinish uchun */
  _retried?: boolean | undefined;
}

/** Fayl yuklab olish — `request` bilan bir xil auth/refresh mantiqi, natija Blob. */
async function requestBlob(path: string, _retried = false): Promise<Blob> {
  const headers: Record<string, string> = {};
  const token = tokens.access();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${PREFIX}${path}`, { headers });
  } catch {
    throw new ApiError(0, "Internetga ulanib bo'lmadi yoki server o'chiq.");
  }

  if (response.status === 401 && !_retried) {
    if (await refreshTokens()) return requestBlob(path, true);
    tokens.clear();
  }
  if (!response.ok) throw await toApiError(response);
  return response.blob();
}

/** Blob'ni brauzerda fayl sifatida saqlatadi. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = false, formData, _retried = false } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = tokens.access();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const init: RequestInit = { method, headers };
  const payload = formData ?? (body !== undefined ? JSON.stringify(body) : null);
  if (payload !== null) init.body = payload;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${PREFIX}${path}`, init);
  } catch {
    throw new ApiError(0, "Internetga ulanib bo'lmadi yoki server o'chiq.");
  }

  // Access token eskirgan bo'lsa bir marta yangilab, qayta urinamiz
  if (response.status === 401 && auth && !_retried) {
    if (await refreshTokens()) {
      return request<T>(path, { ...options, _retried: true });
    }
    tokens.clear();
  }

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Endpointlar
// ---------------------------------------------------------------------------

export const api = {
  // --- auth ---
  async login(username: string, password: string) {
    const pair = await request<TokenPair>("/auth/login", {
      method: "POST",
      body: { username, password },
    });
    tokens.save(pair);
    return pair;
  },

  /** Botdagi "Saytga kirish" tugmasi bergan bir martalik token. */
  async exchangeTelegramToken(token: string) {
    const pair = await request<TokenPair>("/auth/telegram/exchange", {
      method: "POST",
      body: { token },
    });
    tokens.save(pair);
    return pair;
  },

  async logout() {
    try {
      await request<void>("/auth/logout", { method: "POST", auth: true });
    } finally {
      tokens.clear();
    }
  },

  me: () => request<Me>("/auth/me", { auth: true }),

  changePassword: (current_password: string, new_password: string) =>
    request<{ detail: string }>("/auth/change-password", {
      method: "POST",
      auth: true,
      body: { current_password, new_password },
    }),

  // --- ma'lumotnomalar ---
  industries: () => request<Industry[]>("/industries"),

  categories: (industryKey?: string) =>
    request<Category[]>(`/categories${industryKey ? `?industry_key=${industryKey}` : ""}`),

  // --- bizneslar ---
  restaurants: (params: {
    q?: string | undefined;
    industry_key?: string | undefined;
    category_key?: string | undefined;
    min_rating?: number | undefined;
    sort?: "rating" | "new" | "name" | undefined;
    limit?: number | undefined;
    offset?: number | undefined;
  } = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    const suffix = query.toString();
    return request<Page<Restaurant>>(`/restaurants${suffix ? `?${suffix}` : ""}`);
  },

  myRestaurants: () => request<Restaurant[]>("/restaurants/my", { auth: true }),
  restaurant: (id: number) => request<Restaurant>(`/restaurants/${id}`),
  restaurantBySlug: (slug: string) => request<Restaurant>(`/restaurants/slug/${slug}`),

  updateRestaurant: (id: number, changes: Partial<Restaurant>) =>
    request<Restaurant>(`/restaurants/${id}`, { method: "PATCH", auth: true, body: changes }),

  stats: (id: number) => request<DashboardStats>(`/restaurants/${id}/stats`, { auth: true }),

  /** Mijozlar va sharhlar .xlsx — telefonlar faylda ham niqoblangan. */
  exportCustomers: (id: number) => requestBlob(`/restaurants/${id}/customers/export`),

  // --- menyu ---
  menu: (restaurantId: number, onlyAvailable = false) =>
    request<MenuItem[]>(`/restaurants/${restaurantId}/menu?only_available=${onlyAvailable}`),

  createMenuItem: (restaurantId: number, item: Partial<MenuItem>) =>
    request<MenuItem>(`/restaurants/${restaurantId}/menu`, {
      method: "POST",
      auth: true,
      body: item,
    }),

  updateMenuItem: (restaurantId: number, itemId: number, changes: Partial<MenuItem>) =>
    request<MenuItem>(`/restaurants/${restaurantId}/menu/${itemId}`, {
      method: "PATCH",
      auth: true,
      body: changes,
    }),

  deleteMenuItem: (restaurantId: number, itemId: number) =>
    request<{ detail: string }>(`/restaurants/${restaurantId}/menu/${itemId}`, {
      method: "DELETE",
      auth: true,
    }),

  // --- sharhlar ---
  reviews: (params: {
    restaurant_id: number;
    status?: ReviewStatus | undefined;
    rating?: number | undefined;
    limit?: number | undefined;
    offset?: number | undefined;
  }) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) query.set(key, String(value));
    });
    // Egasi barcha statusdagi sharhlarni ko'rishi uchun token yuboriladi
    return request<Page<Review>>(`/reviews?${query}`, { auth: tokens.isLoggedIn() });
  },

  moderateReview: (id: number, status: ReviewStatus, moderation_note?: string) =>
    request<Review>(`/reviews/${id}/moderate`, {
      method: "PATCH",
      auth: true,
      body: { status, moderation_note: moderation_note ?? null },
    }),

  replyToReview: (id: number, text: string) =>
    request<Review>(`/reviews/${id}/reply`, { method: "POST", auth: true, body: { text } }),

  deleteReview: (id: number) =>
    request<{ detail: string }>(`/reviews/${id}`, { method: "DELETE", auth: true }),

  // --- rasm yuklash ---
  async uploadImage(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    return request<{ url: string }>("/uploads/image", {
      method: "POST",
      auth: true,
      formData,
    });
  },

  // --- BotBuilder ---
  bots: (restaurantId: number) =>
    request<BotInstance[]>(`/restaurants/${restaurantId}/bots`, { auth: true }),

  submitQuestionnaire: (
    restaurantId: number,
    payload: { purpose: string; languages: Language[]; features: string[]; tone: string | null },
  ) =>
    request<BotInstance>(`/restaurants/${restaurantId}/bots/questionnaire`, {
      method: "POST",
      auth: true,
      body: payload,
    }),

  botConfig: (restaurantId: number, botId: number) =>
    request<Record<string, unknown>>(`/restaurants/${restaurantId}/bots/${botId}/config`, {
      auth: true,
    }),

  setBotToken: (restaurantId: number, botId: number, token: string) =>
    request<BotInstance>(`/restaurants/${restaurantId}/bots/${botId}/token`, {
      method: "POST",
      auth: true,
      body: { token },
    }),

  startBot: (restaurantId: number, botId: number) =>
    request<BotInstance>(`/restaurants/${restaurantId}/bots/${botId}/start`, {
      method: "POST",
      auth: true,
    }),

  stopBot: (restaurantId: number, botId: number) =>
    request<BotInstance>(`/restaurants/${restaurantId}/bots/${botId}/stop`, {
      method: "POST",
      auth: true,
    }),
};
