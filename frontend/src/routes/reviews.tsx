import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Check, Reply, Trash2, X } from "lucide-react";
import { useState } from "react";

import { AppLayout, ErrorNote, SectionTitle } from "../components/AppLayout";
import { Toast, useToast } from "../components/Toast";
import { api, ApiError, type Restaurant, type Review, type ReviewStatus } from "../lib/api";
import { reviewStatusLabel } from "../lib/labels";

export const Route = createFileRoute("/reviews")({
  head: () => ({ meta: [{ title: "Sharhlar — Restaurant CRM" }] }),
  component: () => <AppLayout>{({ restaurant }) => <Reviews restaurant={restaurant} />}</AppLayout>,
});

const FILTERS: { key: ReviewStatus | "all"; label: string }[] = [
  { key: "all", label: "Hammasi" },
  { key: "pending", label: "Kutilmoqda" },
  { key: "approved", label: "Tasdiqlangan" },
  { key: "rejected", label: "Rad etilgan" },
];

function Reviews({ restaurant }: { restaurant: Restaurant }) {
  const queryClient = useQueryClient();
  const { toast, show, dismiss } = useToast();
  const [filter, setFilter] = useState<ReviewStatus | "all">("all");
  const [replyTo, setReplyTo] = useState<Review | null>(null);
  const [replyText, setReplyText] = useState("");

  const reviews = useQuery({
    queryKey: ["reviews", restaurant.id, filter],
    queryFn: () =>
      api.reviews({
        restaurant_id: restaurant.id,
        status: filter === "all" ? undefined : filter,
        limit: 50,
      }),
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["reviews", restaurant.id] });
    queryClient.invalidateQueries({ queryKey: ["stats", restaurant.id] });
    queryClient.invalidateQueries({ queryKey: ["restaurants", "my"] });
  }

  function onError(exc: unknown) {
    show(exc instanceof ApiError ? exc.message : "Xatolik yuz berdi", "error");
  }

  const moderate = useMutation({
    mutationFn: ({ id, status }: { id: number; status: ReviewStatus }) =>
      api.moderateReview(id, status),
    onSuccess: (_data, variables) => {
      refresh();
      show(variables.status === "approved" ? "Sharh tasdiqlandi" : "Sharh rad etildi");
    },
    onError,
  });

  const reply = useMutation({
    mutationFn: ({ id, text }: { id: number; text: string }) => api.replyToReview(id, text),
    onSuccess: () => {
      refresh();
      setReplyTo(null);
      setReplyText("");
      show("Javob yuborildi — mijozga Telegramda xabar boradi");
    },
    onError,
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteReview(id),
    onSuccess: () => {
      refresh();
      show("Sharh o'chirildi");
    },
    onError,
  });

  if (reviews.isError) return <ErrorNote error={reviews.error} />;

  const items = reviews.data?.items ?? [];

  return (
    <>
      <SectionTitle
        title="Sharhlar"
        subtitle="Mijoz fikrlarini tasdiqlang va javob yozing."
      />

      <div className="filter-row">
        <div className="tabs">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              className={filter === item.key ? "selected" : ""}
              onClick={() => setFilter(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {reviews.isLoading && <p className="muted">Yuklanmoqda...</p>}
      {!reviews.isLoading && items.length === 0 && (
        <div className="panel" style={{ padding: 32, textAlign: "center" }}>
          <p className="muted">
            Bu bo'limda sharh yo'q. Mijozlar Telegram bot orqali sharh qoldiradi.
          </p>
        </div>
      )}

      <div className="panel table-panel">
        {items.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Mijoz</th>
                <th>Baho</th>
                <th>Fikr</th>
                <th>Sana</th>
                <th>Holat</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((review) => (
                <tr key={review.id}>
                  <td>
                    <div className="person-cell">
                      <span className="avatar avatar-soft">
                        {(review.author?.display_name ?? "M").charAt(0)}
                      </span>
                      <b>{review.author?.display_name ?? "Mehmon"}</b>
                    </div>
                  </td>
                  <td>
                    <b>{"★".repeat(review.rating)}</b>
                  </td>
                  <td style={{ maxWidth: 340 }}>
                    {review.text ?? <span className="muted">matnsiz</span>}
                    {review.photos.length > 0 && (
                      <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                        {review.photos.map((url) => (
                          <a key={url} href={url} target="_blank" rel="noreferrer">
                            <img
                              src={url}
                              alt="Sharh rasmi"
                              style={{ width: 44, height: 44, objectFit: "cover", borderRadius: 8 }}
                            />
                          </a>
                        ))}
                      </div>
                    )}
                    {review.owner_reply && (
                      <div className="owner-reply">
                        <b>Javobingiz:</b> {review.owner_reply}
                      </div>
                    )}
                  </td>
                  <td className="muted">
                    {new Date(review.created_at).toLocaleDateString("uz-UZ")}
                  </td>
                  <td>
                    <span className={`status status-${review.status}`}>
                      {reviewStatusLabel(review.status)}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 4 }}>
                      {review.status !== "approved" && (
                        <button
                          className="icon-button"
                          title="Tasdiqlash"
                          disabled={moderate.isPending}
                          onClick={() => moderate.mutate({ id: review.id, status: "approved" })}
                        >
                          <Check size={15} />
                        </button>
                      )}
                      {review.status !== "rejected" && (
                        <button
                          className="icon-button"
                          title="Rad etish"
                          disabled={moderate.isPending}
                          onClick={() => moderate.mutate({ id: review.id, status: "rejected" })}
                        >
                          <X size={15} />
                        </button>
                      )}
                      <button
                        className="icon-button"
                        title="Javob yozish"
                        onClick={() => {
                          setReplyTo(review);
                          setReplyText(review.owner_reply ?? "");
                        }}
                      >
                        <Reply size={15} />
                      </button>
                      <button
                        className="icon-button danger-icon"
                        title="O'chirish"
                        disabled={remove.isPending}
                        onClick={() => remove.mutate(review.id)}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {replyTo && (
        <div
          className="modal-backdrop"
          onMouseDown={(e) => e.target === e.currentTarget && setReplyTo(null)}
        >
          <div className="modal">
            <div className="modal-head">
              <h2>Sharhga javob</h2>
              <button className="icon-button" onClick={() => setReplyTo(null)}>
                <X size={18} />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (replyText.trim()) reply.mutate({ id: replyTo.id, text: replyText.trim() });
              }}
            >
              <p className="muted" style={{ marginBottom: 12 }}>
                {"★".repeat(replyTo.rating)} — {replyTo.text ?? "matnsiz"}
              </p>
              <label>
                Javobingiz
                <textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Fikringiz uchun rahmat!"
                  required
                  maxLength={2000}
                />
              </label>
              <div className="modal-actions">
                <button type="button" className="button secondary" onClick={() => setReplyTo(null)}>
                  Bekor qilish
                </button>
                <button className="button primary" type="submit" disabled={reply.isPending}>
                  <Check size={16} /> {reply.isPending ? "Yuborilmoqda..." : "Yuborish"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <Toast toast={toast} dismiss={dismiss} />
    </>
  );
}
