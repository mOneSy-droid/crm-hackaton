import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { LogIn, Send, Utensils } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { api, ApiError, tokens } from "../lib/api";

export const Route = createFileRoute("/login")({
  head: () => ({ meta: [{ title: "Kirish — Restaurant CRM" }] }),
  component: Login,
});

function Login() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Allaqachon kirgan bo'lsa kabinetga
  useEffect(() => {
    if (tokens.isLoggedIn()) navigate({ to: "/dashboard", replace: true });
  }, [navigate]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.login(username.trim(), password);
      await queryClient.invalidateQueries();
      navigate({ to: "/dashboard", replace: true });
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : "Kirib bo'lmadi");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="brand" style={{ justifyContent: "center", marginBottom: 24 }}>
          <span className="brand-mark">
            <Utensils size={17} />
          </span>
          <span>
            restaurant<b>CRM</b>
          </span>
        </div>

        <h1>Kabinetga kirish</h1>
        <p className="auth-sub">Login va parol Telegram botda ro'yxatdan o'tganda berilgan.</p>

        <form onSubmit={submit}>
          <label>
            Login
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              placeholder="masalan: oshmarkazi_a7f2c"
              required
            />
          </label>
          <label>
            Parol
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          <button className="button primary" type="submit" disabled={busy} style={{ width: "100%" }}>
            <LogIn size={16} /> {busy ? "Tekshirilmoqda..." : "Kirish"}
          </button>
        </form>

        <div className="auth-divider">
          <span>yoki</span>
        </div>

        <a className="button secondary" href="https://t.me/CrmHackaton_bot" style={{ width: "100%" }}>
          <Send size={16} /> Telegram orqali kirish
        </a>
        <p className="auth-hint">
          Botda «Saytga kirish» tugmasini bossangiz — login va parolsiz kirasiz.
        </p>
      </div>
    </div>
  );
}
