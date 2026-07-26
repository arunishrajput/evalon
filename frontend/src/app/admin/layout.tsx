"use client";

import { Navbar } from "@/components/layout/Navbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const ADMIN_LINKS = [
  { href: "/admin", label: "Hackathons" },
  { href: "/admin/hackathons/new", label: "New hackathon" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { ready } = useRequireAuth("admin");

  if (!ready) {
    return <div className="flex min-h-screen items-center justify-center bg-background text-gray-500">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar links={ADMIN_LINKS} />
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">{children}</div>
    </div>
  );
}
