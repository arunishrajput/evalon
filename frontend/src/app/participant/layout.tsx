"use client";

import { Navbar } from "@/components/layout/Navbar";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const PARTICIPANT_LINKS = [{ href: "/participant/hackathons", label: "Hackathons" }];

export default function ParticipantLayout({ children }: { children: React.ReactNode }) {
  const { ready } = useRequireAuth("participant");

  if (!ready) {
    return <div className="flex min-h-screen items-center justify-center bg-background text-gray-500">Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar links={PARTICIPANT_LINKS} />
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">{children}</div>
    </div>
  );
}
