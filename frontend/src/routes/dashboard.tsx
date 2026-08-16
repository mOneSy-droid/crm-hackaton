import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { MessageSquare, ShieldCheck, Star, Utensils } from "lucide-react";

import { AppLayout, ErrorNote, SectionTitle } from "../components/AppLayout";
import { api, type DashboardStats, type Restaurant, type Review } from "../lib/api";
import { catalogLabel, itemLabel, reviewStatusLabel } from "../lib/labels";

export const Route = createFileRoute("/dashboard")({
  head: () => ({ meta: [{ title: "Boshqaruv — Restaurant CRM" }] }),
  component: () => <AppLayout>{({ restaurant }) => <Dashboard restaurant={restaurant} />}</AppLayout>,
});

function Dashboard({ restaurant }: { restaurant: Restaurant }) {
  const stats = useQuery<DashboardStats>({
    queryKey: ["stats", restaurant.id],
    queryFn: () => api.stats(restaurant.id),
  });

  const recent = useQuery({
    queryKey: ["reviews", restaurant.id, "recent"],
    queryFn: () => api.reviews({ restaurant_id: restaurant.id, limit: 5 }),
  });

  if (stats.isError) return <ErrorNote error={stats.error} />;

  const data = stats.data;
  const cards: [string, string, string, typeof Star][] = [
    ["Reyting", data ? data.rating_avg.toFixed(1) : "—", `${data?.rating_count ?? 0} ta sharh`, Star],
    ["Kutayotgan sharhlar", String(data?.reviews_pending ?? 0), "Moderatsiya kerak", MessageSquare],
    ["Oxirgi 7 kun", String(data?.reviews_last_7_days ?? 0), "yangi sharh", MessageSquare],
    [
      catalogLabel(restaurant.industry),
      String(data?.menu_items ?? 0),
      `ta ${itemLabel(restaurant.industry).toLowerCase()}`,
      Utensils,
    ],
  ];

  const breakdown = data?.rating_breakdown ?? {};
  const maxCount = Math.max(1, ...Object.values(breakdown));

  return (
    <>
      <SectionTitle
        title={`Salom, ${restaurant.name}`}
        subtitle="Bugungi holat va oxirgi sharhlar."
        action={
          <Link className="button primary" to="/reviews">
            <MessageSquare size={17} /> Sharhlarni ko'rish
          </Link>
        }
      />

      {!restaurant.is_verified && (
        <div className="alert-banner">
          <ShieldCheck size={18} />
          <div>
            <b>Biznesingiz hali tasdiqlanmagan</b>
            <p>Administrator tasdiqlagach profilingiz qidiruvda yuqoriroq chiqadi.</p>
          </div>
        </div>
      )}

      <div className="stats-grid">
        {cards.map(([label, value, hint, Icon]) => (
          <div className="stat-card" key={label}>
            <div className="stat-head">
              <span>{label}</span>
              <span className="stat-icon">
                <Icon size={18} />
              </span>
            </div>
            <strong>{stats.isLoading ? "…" : value}</strong>
            <div className="stat-trend muted-trend">{hint}</div>
          </div>
        ))}
      </div>

      <div className="dashboard-grid lower">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>Yulduzlar taqsimoti</h2>
              <p>Tasdiqlangan sharhlar bo'yicha</p>
            </div>
          </div>
          {[5, 4, 3, 2, 1].map((star) => {
            const count = breakdown[String(star)] ?? 0;
            return (
              <div className="ranking" key={star}>
                <span className="rank-dot">{star}</span>
                <div>
                  <b>
                    {star} yulduz — {count} ta
                  </b>
                  <div className="progress">
                    <i style={{ width: `${(count / maxCount) * 100}%` }} />
                  </div>
                </div>
                <strong>{count}</strong>
              </div>
            );
          })}
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>Oxirgi sharhlar</h2>
              <p>Eng yangi mijoz fikrlari</p>
            </div>
            <Link className="text-button" to="/reviews">
              Hammasi
            </Link>
          </div>
          {recent.isLoading && <p className="muted">Yuklanmoqda...</p>}
          {recent.data?.items.length === 0 && <p className="muted">Hozircha sharh yo'q.</p>}
          <div className="order-list">
            {recent.data?.items.map((review: Review) => (
              <div className="order-row" key={review.id}>
                <span className="order-id">{"★".repeat(review.rating)}</span>
                <div>
                  <b>{review.author?.display_name ?? "Mehmon"}</b>
                  <small>{review.text ?? "—"}</small>
                </div>
                <span className={`status status-${review.status}`}>
                  {reviewStatusLabel(review.status)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
