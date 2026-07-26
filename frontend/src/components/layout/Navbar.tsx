"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/auth";
import { authApi } from "@/lib/api";
import { initials } from "@/lib/utils";

interface NavbarProps {
  links: { href: string; label: string }[];
}

export function Navbar({ links }: NavbarProps) {
  const router = useRouter();
  const { user, refreshToken, logout } = useAuthStore();

  const handleLogout = async () => {
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken);
      } catch {
        // logout locally regardless of server response
      }
    }
    logout();
    router.replace("/auth/login");
  };

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-background/80 backdrop-blur print:hidden">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-8">
          <Link href="/" className="text-lg font-bold tracking-tight text-white">
            EVAL<span className="text-accent">ON</span>
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="rounded-md px-3 py-2 text-sm font-medium text-gray-400 transition-colors hover:bg-white/5 hover:text-white"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {user && (
            <div className="flex items-center gap-2">
              <Avatar>
                <AvatarFallback>{initials(user.full_name || user.email)}</AvatarFallback>
              </Avatar>
              <span className="hidden text-sm text-gray-300 sm:inline">{user.full_name || user.email}</span>
            </div>
          )}
          <Button variant="ghost" size="icon" onClick={handleLogout} aria-label="Log out">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <nav className="flex items-center gap-1 overflow-x-auto border-t border-white/5 px-4 py-1.5 md:hidden">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="whitespace-nowrap rounded-md px-3 py-1.5 text-sm text-gray-400 hover:bg-white/5 hover:text-white"
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
