import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { CenteredNotice } from "../components/AppLayout";
import { api, ApiError } from "../lib/api";

/**
 * Telegram botdagi «Saytga kirish» tugmasi shu sahifaga olib keladi:
 *   /auth/telegram?token=<bir_martalik_token>&next=/dashboard
 *
 * Token bir martalik va 15 daqiqa yashaydi.
 */
export const Route = createFileRoute("/auth/telegram")({
  validateSearch: (search: Record<string, unknown>) => ({
    token: typeof search["token"] === "string" ? search["token"] : "",
    next: typeof search["next"] === "string" ? search["next"] : "/dashboard",
  }),
  component: TelegramAuth,
});

function TelegramAuth() {
  const { token, next } = Route.useSearch();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  // React 19 StrictMode dev'da effektni ikki marta ishga tushiradi —
  // token bir martalik bo'lgani uchun ikkinchi urinish 401 beradi
  const exchanged = useRef(false);

  useEffect(() => {
    if (exchanged.current) return;
    exchanged.current = true;

    if (!token) {
      setError("Link to'liq emas. Botdan yangi link oling.");
      return;
    }

    api
      .exchangeTelegramToken(token)
      .then(async () => {
        await queryClient.invalidateQueries();
        navigate({ to: next.startsWith("/") ? next : "/dashboard", replace: true });
      })
      .catch((exc: unknown) => {
        setError(
          exc instanceof ApiError
            ? exc.message
            : "Kirib bo'lmadi. Botdan yangi link oling.",
        );
      });
  }, [token, next, navigate, queryClient]);

  if (error) {
    return (
      <CenteredNotice
        title="Kirish amalga oshmadi"
        body={error}
        action={
          <a className="button primary" href="https://t.me/CrmHackaton_bot">
            Botni ochish
          </a>
        }
      />
    );
  }

  return <CenteredNotice title="Kirilmoqda..." body="Bir soniya, kabinetingizga o'tkazamiz." />;
}
