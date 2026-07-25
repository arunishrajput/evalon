import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EVALON — AI-Powered Hackathon Evaluation",
  description:
    "Explainable, evidence-backed AI evaluation for hackathon submissions.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
