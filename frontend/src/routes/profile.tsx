import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Check, MapPin } from "lucide-react";
import { useState, type FormEvent } from "react";

import { AppLayout, SectionTitle } from "../components/AppLayout";
import { Toast, useToast } from "../components/Toast";
import { api, ApiError, type Category, type Industry, type Restaurant } from "../lib/api";
import { fieldLabel, localized } from "../lib/labels";

export const Route = createFileRoute("/profile")({
  head: () => ({ meta: [{ title: "Profil — Restaurant CRM" }] }),
  component: () => <AppLayout>{({ restaurant }) => <Profile restaurant={restaurant} />}</AppLayout>,
});

const WORK_HOURS_RE = /^([01]\d|2[0-3]):[0-5]\d\s*-\s*([01]\d|2[0-3]):[0-5]\d$/;

function Profile({ restaurant }: { restaurant: Restaurant }) {
  const queryClient = useQueryClient();
  const { toast, show, dismiss } = useToast();

  // Faqat shu biznes sohasining yo'nalishlari va savollari
  const industries = useQuery<Industry[]>({
    queryKey: ["industries"],
    queryFn: api.industries,
    staleTime: 10 * 60_000,
  });
  const industry = industries.data?.find((item) => item.key === restaurant.industry.key);
  const categories: Category[] = industry?.categories ?? [];
  const extraFields = industry?.fields ?? [];

  const [form, setForm] = useState({
    name: restaurant.name,
    description: restaurant.description ?? "",
    address: restaurant.address ?? "",
    work_hours: restaurant.work_hours ?? "",
    phone: restaurant.phone ?? "",
    category_id: restaurant.category?.id ?? 0,
    logo_url: restaurant.logo_url ?? "",
  });
  const [attributes, setAttributes] = useState<Record<string, string>>(
    restaurant.attributes ?? {},
  );
  const [hoursError, setHoursError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const save = useMutation({
    mutationFn: (changes: Partial<Restaurant>) => api.updateRestaurant(restaurant.id, changes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["restaurants", "my"] });
      show("Profil saqlandi — bot ham yangilangan ma'lumotni ko'rsatadi");
    },
    onError: (exc: unknown) => {
      if (exc instanceof ApiError) {
        const hours = exc.problemFor("work_hours");
        if (hours) setHoursError(hours);
        show(exc.message, "error");
      } else {
        show("Xatolik yuz berdi", "error");
      }
    },
  });

  async function pickLogo(file: File) {
    setUploading(true);
    try {
      const result = await api.uploadImage(file);
      setForm((prev) => ({ ...prev, logo_url: result.url }));
    } catch (exc) {
      show(exc instanceof ApiError ? exc.message : "Rasm yuklanmadi", "error");
    } finally {
      setUploading(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setHoursError(null);

    // Backend ham tekshiradi, lekin bu yerda ushlasak foydalanuvchi
    // 422 xatosini kutib o'tirmaydi
    if (form.work_hours && !WORK_HOURS_RE.test(form.work_hours)) {
      setHoursError("Ish vaqti 09:00-23:00 ko'rinishida bo'lishi kerak");
      return;
    }

    save.mutate({
      name: form.name.trim(),
      description: form.description.trim() || null,
      address: form.address.trim() || null,
      work_hours: form.work_hours.trim() || null,
      phone: form.phone.trim() || null,
      category_id: form.category_id || null,
      logo_url: form.logo_url || null,
      attributes,
    } as Partial<Restaurant>);
  }

  return (
    <>
      <SectionTitle title="Profil" subtitle="Bu ma'lumotlar ochiq sahifada va botda ko'rinadi." />

      <div className="settings-grid">
        <div className="panel settings-nav">
          <button className="selected">Asosiy ma'lumot</button>
          <div style={{ padding: "14px 16px", borderTop: "1px solid var(--border)" }}>
            <div className="muted" style={{ fontSize: 13 }}>
              <b style={{ display: "block", color: "var(--text)" }}>Joylashuv</b>
              {restaurant.latitude != null ? (
                <a
                  href={`https://maps.google.com/?q=${restaurant.latitude},${restaurant.longitude}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-button"
                  style={{ padding: 0, marginTop: 6 }}
                >
                  <MapPin size={14} /> Xaritada ko'rish
                </a>
              ) : (
                "Botda yuborilmagan"
              )}
              <p style={{ marginTop: 8 }}>Joylashuvni faqat bot orqali o'zgartirish mumkin.</p>
            </div>
          </div>
        </div>

        <div className="panel settings-content">
          <h2>Biznes ma'lumotlari</h2>
          <p>O'zgarishlar darhol saytda va botda aks etadi.</p>

          <form onSubmit={submit}>
            <label>
              Nomi
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                minLength={2}
                maxLength={150}
              />
            </label>

            <label>
              Tavsif
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                maxLength={2000}
              />
            </label>

            <label>
              Manzil
              <input
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                maxLength={300}
              />
            </label>

            <label>
              Ish vaqti
              <input
                value={form.work_hours}
                onChange={(e) => setForm({ ...form, work_hours: e.target.value })}
                placeholder="09:00-23:00"
              />
            </label>
            {hoursError && (
              <div className="auth-error" role="alert">
                {hoursError}
              </div>
            )}

            <label>
              Telefon
              <input
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                maxLength={20}
              />
            </label>

            <label>
              Yo'nalish
              <select
                value={form.category_id}
                onChange={(e) => setForm({ ...form, category_id: Number(e.target.value) })}
              >
                <option value={0}>Tanlanmagan</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {localized(category, "name")}
                  </option>
                ))}
              </select>
            </label>

            {/* Sohaga xos savollar — backenddagi `Industry.fields` bo'yicha chiziladi.
                Yangi soha qo'shilsa bu yerga kod yozilmaydi. */}
            {extraFields.map((field) => (
              <label key={field.key}>
                {fieldLabel(field.label)}
                {field.type === "choice" ? (
                  <select
                    value={attributes[field.key] ?? ""}
                    onChange={(e) =>
                      setAttributes({ ...attributes, [field.key]: e.target.value })
                    }
                  >
                    <option value="">Tanlanmagan</option>
                    {field.choices.map((choice) => (
                      <option key={choice} value={choice}>
                        {choice}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={field.type === "number" ? "number" : "text"}
                    value={attributes[field.key] ?? ""}
                    onChange={(e) =>
                      setAttributes({ ...attributes, [field.key]: e.target.value })
                    }
                  />
                )}
              </label>
            ))}

            <label>
              Logotip
              <input
                type="file"
                accept="image/*"
                onChange={(e) => e.target.files?.[0] && pickLogo(e.target.files[0])}
              />
            </label>
            {uploading && <p className="muted">Yuklanmoqda...</p>}
            {form.logo_url && (
              <img
                src={form.logo_url}
                alt="Logotip"
                style={{ width: 96, height: 96, objectFit: "cover", borderRadius: 12 }}
              />
            )}

            <button className="button primary" type="submit" disabled={save.isPending || uploading}>
              <Check size={16} /> {save.isPending ? "Saqlanmoqda..." : "Saqlash"}
            </button>
          </form>
        </div>
      </div>

      <Toast toast={toast} dismiss={dismiss} />
    </>
  );
}
