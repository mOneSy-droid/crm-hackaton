import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft, Clock, MapPin, Phone, Send, Star, Utensils } from "lucide-react";
import { useEffect } from "react";

import { CenteredNotice, useDarkMode } from "../components/AppLayout";
import { api, type Restaurant } from "../lib/api";
import { catalogLabel, fieldLabel, industryName, localized } from "../lib/labels";

/** Biznesning ochiq sahifasi. Backend `login_url` va QR uchun shu manzilni beradi. */
export const Route = createFileRoute("/r/$slug")({
  head: () => ({ meta: [{ title: "Biznes — Restaurant CRM" }] }),
  component: PublicRestaurant,
});

const BOT_URL = "https://t.me/CrmHackaton_bot";

function money(value: number | null) {
  return value === null ? "" : `${value.toLocaleString("uz-UZ")} so'm`;
}

function PublicRestaurant() {
  const { slug } = Route.useParams();
  useDarkMode();

  const restaurant = useQuery<Restaurant>({
    queryKey: ["restaurant", "slug", slug],
    queryFn: () => api.restaurantBySlug(slug),
    retry: false,
  });

  const menu = useQuery({
    queryKey: ["menu", restaurant.data?.id],
    queryFn: () => api.menu(restaurant.data!.id, true),
    enabled: Boolean(restaurant.data),
  });

  // Savol matnini olish uchun soha tavsifi kerak
  const industries = useQuery({
    queryKey: ["industries"],
    queryFn: api.industries,
    staleTime: 10 * 60_000,
  });

  const reviews = useQuery({
    queryKey: ["reviews", restaurant.data?.id, "public"],
    queryFn: () => api.reviews({ restaurant_id: restaurant.data!.id, limit: 20 }),
    enabled: Boolean(restaurant.data),
  });

  // Sarlavha ma'lumot kelgach aniqlanadi (nomi oldindan noma'lum)
  useEffect(() => {
    if (restaurant.data) document.title = `${restaurant.data.name} — Restaurant CRM`;
  }, [restaurant.data]);

  if (restaurant.isLoading) return <CenteredNotice title="Yuklanmoqda..." />;

  if (restaurant.isError || !restaurant.data) {
    return (
      <CenteredNotice
        title="Topilmadi"
        body="Bu manzildagi biznes mavjud emas yoki yopilgan."
        action={
          <Link className="button primary" to="/">
            Bosh sahifa
          </Link>
        }
      />
    );
  }

  const data = restaurant.data;

  const industrySpec = industries.data?.find((item) => item.key === data.industry.key);
  const industryFacts = (industrySpec?.fields ?? [])
    .map((field) => ({ label: fieldLabel(field.label), value: data.attributes[field.key] ?? "" }))
    .filter((fact) => fact.value);

  return (
    <div className="public-page">
      <header className="landing-top">
        <Link to="/" className="text-button">
          <ArrowLeft size={16} /> Barchasi
        </Link>
        <a className="button primary" href={BOT_URL} target="_blank" rel="noreferrer">
          <Send size={15} /> Sharh qoldirish
        </a>
      </header>

      <section className="public-hero">
        <div className="public-logo">
          {data.logo_url ? (
            <img src={data.logo_url} alt={data.name} />
          ) : (
            <Utensils size={38} />
          )}
        </div>
        <div>
          <span className="eyebrow">
            {data.industry.icon}{" "}
            {localized(data.category, "name") || industryName(data.industry)}
          </span>
          <h1>{data.name}</h1>
          {data.rating_count > 0 ? (
            <div className="public-rating">
              <Star size={18} /> <b>{data.rating_avg.toFixed(1)}</b>
              <span>{data.rating_count} ta sharh</span>
            </div>
          ) : (
            <p className="muted">Hozircha sharh yo'q — birinchi bo'ling!</p>
          )}
          <p className="public-desc">{data.description}</p>
          <div className="restaurant-meta">
            {data.address && (
              <span>
                <MapPin size={14} /> {data.address}
              </span>
            )}
            {data.work_hours && (
              <span>
                <Clock size={14} /> {data.work_hours}
              </span>
            )}
            {data.phone && (
              <span>
                <Phone size={14} /> {data.phone}
              </span>
            )}
          </div>
          {data.latitude != null && (
            <a
              className="text-button"
              href={`https://maps.google.com/?q=${data.latitude},${data.longitude}`}
              target="_blank"
              rel="noreferrer"
              style={{ paddingLeft: 0 }}
            >
              <MapPin size={14} /> Xaritada ochish
            </a>
          )}

          {/* Sohaga xos ma'lumotlar: do'konda yetkazib berish,
              klinikada qabul turi va h.k. */}
          {industryFacts.length > 0 && (
            <div className="fact-row">
              {industryFacts.map(({ label, value }) => (
                <span className="fact-chip" key={label}>
                  <b>{label}</b> {value}
                </span>
              ))}
            </div>
          )}
        </div>
      </section>

      {(menu.data?.length ?? 0) > 0 && (
        <section className="public-section">
          <h2>{catalogLabel(data.industry)}</h2>
          <div className="menu-grid">
            {menu.data?.map((item) => (
              <div className="menu-card" key={item.id}>
                <div className="food-image food-amber">
                  {item.photo_url ? (
                    <img
                      src={item.photo_url}
                      alt={item.name}
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    />
                  ) : (
                    <Utensils size={26} />
                  )}
                </div>
                <div className="menu-copy">
                  <span className="eyebrow">{item.section ?? "Umumiy"}</span>
                  <h3>{item.name}</h3>
                  <p>{item.description ?? ""}</p>
                  <div className="menu-footer">
                    <strong>{money(item.price)}</strong>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="public-section">
        <h2>Sharhlar</h2>
        {reviews.isLoading && <p className="muted">Yuklanmoqda...</p>}
        {reviews.data?.items.length === 0 && (
          <p className="muted">
            Hozircha sharh yo'q. Botda «Sharh qoldirish» tugmasini bosing.
          </p>
        )}
        <div className="review-list">
          {reviews.data?.items.map((review) => (
            <article className="review-card" key={review.id}>
              <div className="review-head">
                <span className="avatar avatar-soft">
                  {(review.author?.display_name ?? "M").charAt(0)}
                </span>
                <div>
                  <b>{review.author?.display_name ?? "Mehmon"}</b>
                  <small>{new Date(review.created_at).toLocaleDateString("uz-UZ")}</small>
                </div>
                <span className="review-stars">{"★".repeat(review.rating)}</span>
              </div>
              {review.text && <p>{review.text}</p>}
              {review.photos.length > 0 && (
                <div className="review-photos">
                  {review.photos.map((url) => (
                    <a key={url} href={url} target="_blank" rel="noreferrer">
                      <img src={url} alt="" />
                    </a>
                  ))}
                </div>
              )}
              {review.owner_reply && (
                <div className="owner-reply">
                  <b>{data.name}:</b> {review.owner_reply}
                </div>
              )}
            </article>
          ))}
        </div>
      </section>

      <footer className="landing-foot">
        <span>Restaurant CRM</span>
        <a href={BOT_URL} target="_blank" rel="noreferrer">
          @CrmHackaton_bot
        </a>
      </footer>
    </div>
  );
}
