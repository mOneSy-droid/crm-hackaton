import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { api, tokens, type Me, type Restaurant } from "./api";

/** SSR paytida localStorage yo'q — brauzerga o'tgach true bo'ladi. */
export function useHydrated() {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);
  return hydrated;
}

export function useSession() {
  const hydrated = useHydrated();
  const loggedIn = hydrated && tokens.isLoggedIn();

  const query = useQuery<Me>({
    queryKey: ["me"],
    queryFn: api.me,
    enabled: loggedIn,
    retry: false,
    staleTime: 60_000,
  });

  return {
    me: query.data,
    isLoading: !hydrated || (loggedIn && query.isLoading),
    isLoggedIn: loggedIn && !query.isError,
    hydrated,
  };
}

export function useMyRestaurants() {
  const { isLoggedIn } = useSession();
  return useQuery<Restaurant[]>({
    queryKey: ["restaurants", "my"],
    queryFn: api.myRestaurants,
    enabled: isLoggedIn,
    staleTime: 30_000,
  });
}

/**
 * Kabinet sahifalari uchun: kirmagan foydalanuvchini /login ga yuboradi.
 * Faol biznesni ham qaytaradi (bir nechtasi bo'lsa birinchisi).
 */
export function useRequireAuth() {
  const navigate = useNavigate();
  const { me, isLoading, isLoggedIn, hydrated } = useSession();
  const restaurants = useMyRestaurants();

  useEffect(() => {
    if (hydrated && !isLoading && !isLoggedIn) {
      navigate({ to: "/login", replace: true });
    }
  }, [hydrated, isLoading, isLoggedIn, navigate]);

  return {
    me,
    isLoading: isLoading || restaurants.isLoading,
    isLoggedIn,
    restaurants: restaurants.data ?? [],
    restaurant: restaurants.data?.[0],
  };
}

export function useLogout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return async () => {
    await api.logout().catch(() => tokens.clear());
    queryClient.clear();
    navigate({ to: "/login", replace: true });
  };
}
