import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Check, Plus, Trash2, Utensils, X } from "lucide-react";
import { useState, type FormEvent } from "react";

import { AppLayout, ErrorNote, SectionTitle } from "../components/AppLayout";
import { Toast, useToast } from "../components/Toast";
import { api, ApiError, type MenuItem, type Restaurant } from "../lib/api";
import { catalogLabel, itemLabel } from "../lib/labels";

export const Route = createFileRoute("/menu")({
  head: () => ({ meta: [{ title: "Katalog — Restaurant CRM" }] }),
  component: () => <AppLayout>{({ restaurant }) => <MenuPage restaurant={restaurant} />}</AppLayout>,
});

function money(value: number | null) {
  if (value === null) return "—";
  return `${value.toLocaleString("uz-UZ")} so'm`;
}

function MenuPage({ restaurant }: { restaurant: Restaurant }) {
  const queryClient = useQueryClient();
  const { toast, show, dismiss } = useToast();
  const [editing, setEditing] = useState<MenuItem | "new" | null>(null);

  // Yorliqlar sohadan keladi: Menyu/Taom, Katalog/Mahsulot, Xizmatlar/Xizmat
  const catalog = catalogLabel(restaurant.industry);
  const item = itemLabel(restaurant.industry);

  const menu = useQuery({
    queryKey: ["menu", restaurant.id],
    queryFn: () => api.menu(restaurant.id, false),
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["menu", restaurant.id] });
    queryClient.invalidateQueries({ queryKey: ["stats", restaurant.id] });
  }

  function onError(exc: unknown) {
    show(exc instanceof ApiError ? exc.message : "Xatolik yuz berdi", "error");
  }

  const save = useMutation({
    mutationFn: async (payload: { id?: number | undefined; data: Partial<MenuItem> }) =>
      payload.id
        ? api.updateMenuItem(restaurant.id, payload.id, payload.data)
        : api.createMenuItem(restaurant.id, payload.data),
    onSuccess: () => {
      refresh();
      setEditing(null);
      show("Saqlandi");
    },
    onError,
  });

  const toggle = useMutation({
    mutationFn: (item: MenuItem) =>
      api.updateMenuItem(restaurant.id, item.id, { is_available: !item.is_available }),
    onSuccess: () => refresh(),
    onError,
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteMenuItem(restaurant.id, id),
    onSuccess: () => {
      refresh();
      show(`${item} o'chirildi`);
    },
    onError,
  });

  if (menu.isError) return <ErrorNote error={menu.error} />;

  const items = menu.data ?? [];
  const sections = Array.from(new Set(items.map((i) => i.section).filter(Boolean))) as string[];

  return (
    <>
      <SectionTitle
        title={catalog}
        subtitle={`${item} nomlari, narxlari va mavjudligini boshqaring.`}
        action={
          <button className="button primary" onClick={() => setEditing("new")}>
            <Plus size={17} /> {item} qo'shish
          </button>
        }
      />

      {sections.length > 0 && (
        <div className="category-row">
          <button className="selected">Hammasi</button>
          {sections.map((section) => (
            <button key={section}>{section}</button>
          ))}
        </div>
      )}

      {menu.isLoading && <p className="muted">Yuklanmoqda...</p>}
      {!menu.isLoading && items.length === 0 && (
        <div className="panel" style={{ padding: 32, textAlign: "center" }}>
          <p className="muted">
            {catalog} bo'sh. Birinchi {item.toLowerCase()}ni qo'shing.
          </p>
        </div>
      )}

      <div className="menu-grid">
        {items.map((item) => (
          <div className="menu-card" key={item.id}>
            <div className="food-image food-amber">
              {item.photo_url ? (
                <img
                  src={item.photo_url}
                  alt={item.name}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              ) : (
                <Utensils size={30} />
              )}
            </div>
            <div className="menu-copy">
              <div className="menu-top">
                <span className="eyebrow">{item.section ?? "Umumiy"}</span>
                <div style={{ display: "flex", gap: 2 }}>
                  <button className="icon-button" onClick={() => setEditing(item)} title="Tahrirlash">
                    <Check size={15} />
                  </button>
                  <button
                    className="icon-button danger-icon"
                    onClick={() => remove.mutate(item.id)}
                    title="O'chirish"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
              <h3>{item.name}</h3>
              <p>{item.description ?? "Tavsif kiritilmagan."}</p>
              <div className="menu-footer">
                <strong>{money(item.price)}</strong>
                <button
                  className={`toggle ${item.is_available ? "on" : ""}`}
                  onClick={() => toggle.mutate(item)}
                  aria-label="Mavjudligini almashtirish"
                >
                  <i />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <MenuItemModal
          itemLabel={item}
          item={editing === "new" ? null : editing}
          busy={save.isPending}
          close={() => setEditing(null)}
          onSave={(data) =>
            save.mutate({ id: editing === "new" ? undefined : editing.id, data })
          }
          onUploadError={onError}
        />
      )}

      <Toast toast={toast} dismiss={dismiss} />
    </>
  );
}

function MenuItemModal({
  item,
  itemLabel: label,
  busy,
  close,
  onSave,
  onUploadError,
}: {
  item: MenuItem | null;
  itemLabel: string;
  busy: boolean;
  close: () => void;
  onSave: (data: Partial<MenuItem>) => void;
  onUploadError: (exc: unknown) => void;
}) {
  const [name, setName] = useState(item?.name ?? "");
  const [description, setDescription] = useState(item?.description ?? "");
  const [price, setPrice] = useState(item?.price != null ? String(item.price) : "");
  const [section, setSection] = useState(item?.section ?? "");
  const [photoUrl, setPhotoUrl] = useState(item?.photo_url ?? "");
  const [uploading, setUploading] = useState(false);

  async function pickPhoto(file: File) {
    setUploading(true);
    try {
      const result = await api.uploadImage(file);
      setPhotoUrl(result.url);
    } catch (exc) {
      onUploadError(exc);
    } finally {
      setUploading(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    onSave({
      name: name.trim(),
      description: description.trim() || null,
      price: price ? Number(price) : null,
      section: section.trim() || null,
      photo_url: photoUrl || null,
    });
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div className="modal">
        <div className="modal-head">
          <h2>{item ? `${label}ni tahrirlash` : `Yangi ${label.toLowerCase()}`}</h2>
          <button className="icon-button" onClick={close}>
            <X size={18} />
          </button>
        </div>
        <form onSubmit={submit}>
          <label>
            Nomi
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={150} />
          </label>
          <label>
            Tavsif
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <label>
            Narxi (so'm)
            <input
              type="number"
              min="0"
              step="1000"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
            />
          </label>
          <label>
            Bo'lim
            <input
              value={section}
              onChange={(e) => setSection(e.target.value)}
              placeholder="Masalan: Salatlar"
            />
          </label>
          <label>
            Rasm
            <input
              type="file"
              accept="image/*"
              onChange={(e) => e.target.files?.[0] && pickPhoto(e.target.files[0])}
            />
          </label>
          {uploading && <p className="muted">Rasm yuklanmoqda...</p>}
          {photoUrl && (
            <img
              src={photoUrl}
              alt=""
              style={{ width: 96, height: 96, objectFit: "cover", borderRadius: 10 }}
            />
          )}
          <div className="modal-actions">
            <button type="button" className="button secondary" onClick={close}>
              Bekor qilish
            </button>
            <button className="button primary" type="submit" disabled={busy || uploading}>
              <Check size={16} /> {busy ? "Saqlanmoqda..." : "Saqlash"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
