import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Bot, Check, Pause, Play, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";

import { AppLayout, ErrorNote, SectionTitle } from "../components/AppLayout";
import { Toast, useToast } from "../components/Toast";
import { api, ApiError, type BotInstance, type Language, type Restaurant } from "../lib/api";

export const Route = createFileRoute("/mybot")({
  head: () => ({ meta: [{ title: "Botim — Restaurant CRM" }] }),
  component: () => <AppLayout>{({ restaurant }) => <MyBot restaurant={restaurant} />}</AppLayout>,
});

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "uz", label: "O'zbek" },
  { code: "ru", label: "Русский" },
  { code: "en", label: "English" },
];

const STATUS_LABEL: Record<BotInstance["status"], string> = {
  draft: "Qoralama",
  pending: "Token kutilmoqda",
  active: "Ishlayapti",
  stopped: "To'xtatilgan",
  failed: "Xatolik",
};

function MyBot({ restaurant }: { restaurant: Restaurant }) {
  const queryClient = useQueryClient();
  const { toast, show, dismiss } = useToast();

  const bots = useQuery({
    queryKey: ["bots", restaurant.id],
    queryFn: () => api.bots(restaurant.id),
  });

  const bot = bots.data?.[0];

  const [purpose, setPurpose] = useState("");
  const [languages, setLanguages] = useState<Language[]>(["uz"]);
  const [features, setFeatures] = useState("");
  const [tone, setTone] = useState("");
  const [token, setToken] = useState("");

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["bots", restaurant.id] });
    queryClient.invalidateQueries({ queryKey: ["stats", restaurant.id] });
  }

  function onError(exc: unknown) {
    show(exc instanceof ApiError ? exc.message : "Xatolik yuz berdi", "error");
  }

  const submitQuestionnaire = useMutation({
    mutationFn: () =>
      api.submitQuestionnaire(restaurant.id, {
        purpose: purpose.trim(),
        languages,
        features: features
          .split(",")
          .map((f) => f.trim())
          .filter(Boolean),
        tone: tone.trim() || null,
      }),
    onSuccess: () => {
      refresh();
      show("Bot logikasi tayyorlandi. Endi @BotFather dan token oling.");
    },
    onError,
  });

  const attachToken = useMutation({
    mutationFn: () => api.setBotToken(restaurant.id, bot!.id, token.trim()),
    onSuccess: (instance) => {
      refresh();
      setToken("");
      show(`@${instance.bot_username} ulandi va ishga tushdi!`);
    },
    onError,
  });

  const toggleBot = useMutation({
    mutationFn: () =>
      bot!.status === "active"
        ? api.stopBot(restaurant.id, bot!.id)
        : api.startBot(restaurant.id, bot!.id),
    onSuccess: () => {
      refresh();
      show("Bot holati yangilandi");
    },
    onError,
  });

  if (bots.isError) return <ErrorNote error={bots.error} />;

  return (
    <>
      <SectionTitle
        title="O'z botim"
        subtitle="Biznesingiz uchun shaxsiy Telegram bot yarating."
      />

      {bots.isLoading && <p className="muted">Yuklanmoqda...</p>}

      {bot && (
        <div className="stats-grid three">
          <div className="stat-card">
            <span className="stat-label">Holat</span>
            <strong>{STATUS_LABEL[bot.status]}</strong>
            {bot.status_detail && <div className="stat-trend muted-trend">{bot.status_detail}</div>}
          </div>
          <div className="stat-card">
            <span className="stat-label">Bot</span>
            <strong>{bot.bot_username ? `@${bot.bot_username}` : "—"}</strong>
            <div className="stat-trend muted-trend">
              {bot.token_hint ? `Token: …${bot.token_hint}` : "Token ulanmagan"}
            </div>
          </div>
          <div className="stat-card">
            <span className="stat-label">Tillar</span>
            <strong>{(bot.languages ?? "uz").toUpperCase().replaceAll(",", " · ")}</strong>
            <div className="stat-trend muted-trend">
              {bot.has_generated_config ? "Logika tayyor" : "Logika yo'q"}
            </div>
          </div>
        </div>
      )}

      <div className="settings-grid">
        <div className="panel settings-content">
          <h2>
            <Sparkles size={18} style={{ verticalAlign: "-3px", marginRight: 6 }} />
            Anketa
          </h2>
          <p>Javoblaringiz asosida bot matnlari va oqimlari avtomatik tayyorlanadi.</p>

          <form
            onSubmit={(event: FormEvent) => {
              event.preventDefault();
              submitQuestionnaire.mutate();
            }}
          >
            <label>
              Bot nima uchun kerak?
              <textarea
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="Masalan: buyurtma qabul qilish va katalogni ko'rsatish"
                required
                minLength={3}
              />
            </label>

            <label>Qaysi tillarda ishlasin?</label>
            <div className="category-row">
              {LANGUAGES.map(({ code, label }) => (
                <button
                  type="button"
                  key={code}
                  className={languages.includes(code) ? "selected" : ""}
                  onClick={() =>
                    setLanguages((prev) =>
                      prev.includes(code)
                        ? prev.filter((item) => item !== code)
                        : [...prev, code],
                    )
                  }
                >
                  {label}
                </button>
              ))}
            </div>

            <label>
              Kerakli funksiyalar
              <input
                value={features}
                onChange={(e) => setFeatures(e.target.value)}
                placeholder="katalog, bron qilish, aksiyalar"
              />
            </label>

            <label>
              Muloqot uslubi
              <input
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                placeholder="do'stona / rasmiy / qisqa"
              />
            </label>

            <button
              className="button primary"
              type="submit"
              disabled={submitQuestionnaire.isPending || languages.length === 0}
            >
              <Sparkles size={16} />
              {submitQuestionnaire.isPending ? "Tayyorlanmoqda..." : "Bot logikasini yaratish"}
            </button>
          </form>
        </div>

        <div className="panel settings-content">
          <h2>
            <Bot size={18} style={{ verticalAlign: "-3px", marginRight: 6 }} />
            Tokenni ulash
          </h2>

          {!bot?.has_generated_config ? (
            <p className="muted">Avval chapdagi anketani to'ldiring.</p>
          ) : (
            <>
              <ol className="steps">
                <li>
                  Telegramda <b>@BotFather</b> ni oching
                </li>
                <li>
                  <code>/newbot</code> yuboring, nom va username tanlang
                </li>
                <li>BotFather bergan tokenni quyiga qo'ying</li>
              </ol>

              <form
                onSubmit={(event: FormEvent) => {
                  event.preventDefault();
                  attachToken.mutate();
                }}
              >
                <label>
                  Bot tokeni
                  <input
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="123456789:AA..."
                    autoComplete="off"
                    required
                  />
                </label>
                <p className="muted" style={{ fontSize: 12 }}>
                  🔒 Token shifrlangan holda saqlanadi va hech qachon qaytarilmaydi.
                </p>
                <button className="button primary" type="submit" disabled={attachToken.isPending}>
                  <Check size={16} /> {attachToken.isPending ? "Tekshirilmoqda..." : "Ulash"}
                </button>
              </form>

              {bot.token_hint && (
                <div className="setting-line" style={{ marginTop: 20 }}>
                  <div>
                    <b>Botni boshqarish</b>
                    <p>
                      {bot.status === "active"
                        ? "Bot hozir ishlab turibdi."
                        : "Bot to'xtatilgan."}
                    </p>
                  </div>
                  <button
                    className="button secondary"
                    onClick={() => toggleBot.mutate()}
                    disabled={toggleBot.isPending}
                  >
                    {bot.status === "active" ? (
                      <>
                        <Pause size={15} /> To'xtatish
                      </>
                    ) : (
                      <>
                        <Play size={15} /> Ishga tushirish
                      </>
                    )}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <Toast toast={toast} dismiss={dismiss} />
    </>
  );
}
