import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { MapPin, Search, Send, Star, Utensils } from "lucide-react";
import { useEffect, useState } from "react";

import { useDarkMode } from "../components/AppLayout";
import { api, tokens, type Industry, type Restaurant } from "../lib/api";
import { localized } from "../lib/labels";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Restaurant CRM — Bizneslar katalogi" },
      {
        name: "description",
        content:
          "Restoran, do'kon, klinika va sport markazlarini toping, sharhlarni o'qing. Biznes egalari uchun: Telegram bot orqali ro'yxatdan o'ting va kabinetdan boshqaring.",
      },
    ],
  }),
  component: Landing,
});

const BOT_URL = "https://t.me/CrmHackaton_bot";

function Landing() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [industryKey, setIndustryKey] = useState<string>("");
  const [categoryKey, setCategoryKey] = useState<string>("");
  const [loggedIn, setLoggedIn] = useState(false);
  useDarkMode();

  useEffect(() => setLoggedIn(tokens.isLoggedIn()), []);

  // Har harfda so'rov yubormaslik uchun kechiktiramiz
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);

  const industries = useQuery<Industry[]>({
    queryKey: ["industries"],
    queryFn: api.industries,
    staleTime: 10 * 60_000,
  });

  // Yo'nalishlar tanlangan soha ichidan — soha almashsa eskisi tozalanadi
  const activeIndustry = industries.data?.find((item) => item.key === industryKey);
  const categories = activeIndustry?.categories ?? [];

  const restaurants = useQuery({
    queryKey: ["restaurants", "public", debounced, industryKey, categoryKey],
    queryFn: () =>
      api.restaurants({
        q: debounced || undefined,
        industry_key: industryKey || undefined,
        category_key: categoryKey || undefined,
        sort: "rating",
        limit: 24,
      }),
  });

  function chooseIndustry(key: string) {
    setIndustryKey(key);
    setCategoryKey("");
  }

  return (
    <div className="landing">
      <header className="landing-top">
        <div className="brand">
          <span className="brand-mark">
            <Utensils size={17} />
          </span>
          <span>
            restaurant<b>CRM</b>
          </span>
        </div>
        <div className="landing-actions">
          <a className="button secondary" href={BOT_URL} target="_blank" rel="noreferrer">
            <Send size={15} /> Biznes qo'shish
          </a>
          {loggedIn ? (
            <button className="button primary" onClick={() => navigate({ to: "/dashboard" })}>
              Kabinet
            </button>
          ) : (
            <Link className="button primary" to="/login">
              Kirish
            </Link>
          )}
        </div>
      </header>

      <section className="landing-hero">
        <h1>Kerakli joyni toping, fikringizni qoldiring</h1>
        <p>
          Restoran, do'kon, klinika yoki sport markazi — biznesingizni Telegram bot orqali
          2 daqiqada ro'yxatdan o'tkazing. SMS ham, hujjat ham kerak emas.
        </p>
        <div className="landing-search">
          <Search size={18} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Nomi yoki manzil bo'yicha qidirish..."
          />
        </div>
      </section>

      <div className="industry-row">
        <button className={industryKey === "" ? "selected" : ""} onClick={() => chooseIndustry("")}>
          Barchasi
        </button>
        {industries.data?.map((industry) => (
          <button
            key={industry.key}
            className={industryKey === industry.key ? "selected" : ""}
            onClick={() => chooseIndustry(industry.key)}
          >
            <span aria-hidden>{industry.icon}</span> {localized(industry, "name")}
          </button>
        ))}
      </div>

      {categories.length > 0 && (
        <div className="category-row landing-categories">
          <button
            className={categoryKey === "" ? "selected" : ""}
            onClick={() => setCategoryKey("")}
          >
            Hamma yo'nalish
          </button>
          {categories.map((category) => (
            <button
              key={category.key}
              className={categoryKey === category.key ? "selected" : ""}
              onClick={() => setCategoryKey(category.key)}
            >
              {localized(category, "name")}
            </button>
          ))}
        </div>
      )}

      <section className="landing-list">
        {restaurants.isLoading && <p className="muted">Yuklanmoqda...</p>}

        {restaurants.isError && (
          <div className="alert-banner">
            <div>
              <b>Ma'lumotni olib bo'lmadi</b>
              <p>Server javob bermayapti. Sahifani yangilab ko'ring.</p>
            </div>
          </div>
        )}

        {restaurants.data?.items.length === 0 && (
          <div className="panel" style={{ padding: 40, textAlign: "center" }}>
            <p className="muted">
              {debounced || categoryKey || industryKey
                ? "Bu shartlarga mos hech narsa topilmadi."
                : "Hozircha ro'yxat bo'sh. Birinchi bo'lib qo'shing!"}
            </p>
          </div>
        )}

        <div className="restaurant-grid">
          {restaurants.data?.items.map((restaurant) => (
            <RestaurantCard key={restaurant.id} restaurant={restaurant} />
          ))}
        </div>

        {restaurants.data && restaurants.data.total > restaurants.data.items.length && (
          <p className="muted" style={{ textAlign: "center", marginTop: 16 }}>
            Jami {restaurants.data.total} ta
          </p>
        )}
      </section>

      <footer className="landing-foot">
        <span>Restaurant CRM — Telegram bot orqali ro'yxatdan o'tish</span>
        <a href={BOT_URL} target="_blank" rel="noreferrer">
          @CrmHackaton_bot
        </a>
      </footer>
    </div>
  );
}

function RestaurantCard({ restaurant }: { restaurant: Restaurant }) {
  return (
    <Link to="/r/$slug" params={{ slug: restaurant.slug }} className="restaurant-card">
      <div className="food-image food-amber">
        {restaurant.logo_url ? (
          <img
            src={restaurant.logo_url}
            alt={restaurant.name}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <Utensils size={30} />
        )}
      </div>
      <div className="menu-copy">
        <div className="menu-top">
          <span className="eyebrow">
            {restaurant.industry.icon}{" "}
            {localized(restaurant.category, "name") || localized(restaurant.industry, "name")}
          </span>
          {restaurant.rating_count > 0 && (
            <span className="rating-chip">
              <Star size={13} /> {restaurant.rating_avg.toFixed(1)}
            </span>
          )}
        </div>
        <h3>{restaurant.name}</h3>
        <p>{restaurant.description ?? "Tavsif kiritilmagan."}</p>
        <div className="restaurant-meta">
          {restaurant.address && (
            <span>
              <MapPin size={13} /> {restaurant.address}
            </span>
          )}
          {restaurant.work_hours && <span>{restaurant.work_hours}</span>}
        </div>
      </div>
    </Link>
  );
}
