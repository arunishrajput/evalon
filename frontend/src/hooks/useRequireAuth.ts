"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { authApi } from "@/lib/api";
import type { UserRole } from "@/lib/types";

/** Client-side auth guard: redirects to /auth/login if no session, and to
 * the other role's home if the current user's role doesn't match. Re-checks
 * /auth/me once on mount so a stale cached user (role changed, deactivated)
 * doesn't silently grant access to a page it shouldn't.
 *
 * Waits for the auth store's zustand `persist` rehydration to finish before
 * treating a missing accessToken as "not logged in" — otherwise a hard page
 * load (refresh, direct link, new tab) always races the localStorage read
 * and bounces an already-logged-in user to /auth/login. */
export function useRequireAuth(requiredRole?: UserRole) {
  const router = useRouter();
  const { user, accessToken, hasHydrated, setUser, logout } = useAuthStore();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!hasHydrated) return;

    if (!accessToken) {
      router.replace("/auth/login");
      return;
    }
    authApi
      .me()
      .then((fresh) => {
        setUser(fresh);
        if (requiredRole && fresh.role !== requiredRole) {
          router.replace(fresh.role === "admin" ? "/admin" : "/participant");
          return;
        }
        setReady(true);
      })
      .catch(() => {
        logout();
        router.replace("/auth/login");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, hasHydrated]);

  return { user, ready };
}
