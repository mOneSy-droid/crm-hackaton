import { Link, useRouterState } from "@tanstack/react-router";
import {
  Bot,
  ChevronDown,
  LayoutDashboard,
  LogOut,
  Menu as MenuIcon,
  MessageSquare,
  Moon,
  PanelLeft,
  Settings,
  Sun,
  Utensils,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { useLogout, useRequireAuth } from "../lib/session";
import { catalogLabel, industryName, localized } from "../lib/labels";
import type { Restaurant } from "../lib/api";

/** `/menu` yorlig'i sohaga qarab o'zgaradi: Menyu / Katalog / Xizmatlar. */
function navItems(catalog: string) {
  return [
    { to: "/dashboard", label: "Boshqaruv", icon: LayoutDashboard },
    { to: "/reviews", label: "Sharhlar", icon: MessageSquare },
    { to: "/menu", label: catalog, icon: MenuIcon },
    { to: "/mybot", label: "Botim", icon: Bot },
    { to: "/profile", label: "Profil", icon: Settings },
  ] as const;
}

export function useDarkMode() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(localStorage.getItem("crm-theme") === "dark");
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("crm-theme", dark ? "dark" : "light");
  }, [dark]);

  return { dark, setDark };
}

/**
 * Kabinet qobig'i: yon panel + yuqori panel.
 * Kirmagan foydalanuvchini `useRequireAuth` /login ga yuboradi.
 */
export function AppLayout({
  children,
  pendingCount,
}: {
  children: (context: { restaurant: Restaurant; restaurants: Restaurant[] }) => ReactNode;
  pendingCount?: number;
}) {
  const { me, isLoading, isLoggedIn, restaurant, restaurants } = useRequireAuth();
  const [collapsed, setCollapsed] = useState(false);
  const { dark, setDark } = useDarkMode();
  const logout = useLogout();
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  if (isLoading) {
    return <CenteredNotice title="Yuklanmoqda..." />;
  }

  if (!isLoggedIn) {
    // useRequireAuth allaqachon /login ga yo'naltirdi
    return <CenteredNotice title="Kirish talab qilinadi" />;
  }

  if (!restaurant) {
    return (
      <CenteredNotice
        title="Sizda hali biznes yo'q"
        body="Biznes Telegram bot orqali qo'shiladi. @CrmHackaton_bot ni oching va /register buyrug'ini yuboring."
      />
    );
  }

  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Utensils size={17} />
          </span>
          <span>
            restaurant<b>CRM</b>
          </span>
        </div>
        <div className="sidebar-label">Kabinet</div>
        <nav>
          {navItems(catalogLabel(restaurant.industry)).map(({ to, label, icon: Icon }) => (
            <Link key={to} to={to} className={pathname === to ? "nav-item active" : "nav-item"}>
              <Icon size={18} />
              <span>{label}</span>
              {to === "/reviews" && pendingCount ? <em>{pendingCount}</em> : null}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="open-pill">
            <span />
            {restaurant.is_verified ? "Tasdiqlangan" : "Tasdiqlanmagan"}
          </div>
          <div className="branch">
            <span className="avatar avatar-orange">
              {restaurant.name.charAt(0).toUpperCase()}
            </span>
            <div>
              <b>{restaurant.name}</b>
              <small>
                {restaurant.industry.icon}{" "}
                {localized(restaurant.category, "name") || industryName(restaurant.industry)}
              </small>
            </div>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <button
            className="icon-button menu-toggle"
            onClick={() => setCollapsed(!collapsed)}
            aria-label="Yon panelni yigish"
          >
            <PanelLeft size={20} />
          </button>
          <div className="search-box">
            <span style={{ fontWeight: 600 }}>{restaurant.name}</span>
          </div>
          <div className="top-actions">
            <a className="date-control" href={`/r/${restaurant.slug}`} target="_blank" rel="noreferrer">
              Ochiq sahifa <ChevronDown size={14} style={{ transform: "rotate(-90deg)" }} />
            </a>
            <button className="icon-button" onClick={() => setDark(!dark)} aria-label="Mavzuni almashtirish">
              {dark ? <Sun size={19} /> : <Moon size={19} />}
            </button>
            <div className="profile">
              <span className="avatar">{(me?.full_name ?? me?.username ?? "?").charAt(0).toUpperCase()}</span>
              <span className="profile-copy">
                <b>{me?.full_name ?? me?.username}</b>
                <small>{me?.role === "admin" ? "Administrator" : "Egasi"}</small>
              </span>
            </div>
            <button className="icon-button" onClick={logout} aria-label="Chiqish" title="Chiqish">
              <LogOut size={19} />
            </button>
          </div>
        </header>

        <div className="content-wrap">{children({ restaurant, restaurants })}</div>
      </main>
    </div>
  );
}

export function CenteredNotice({
  title,
  body,
  action,
}: {
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold text-foreground">{title}</h1>
        {body && <p className="mt-2 text-sm text-muted-foreground">{body}</p>}
        {action && <div className="mt-6">{action}</div>}
      </div>
    </div>
  );
}

export function SectionTitle({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Xatolik yuz berdi";
  return (
    <div className="alert-banner" role="alert">
      <div>
        <b>{message}</b>
      </div>
    </div>
  );
}
