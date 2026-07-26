import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// Declared in tailwind.config.js's fontFamily since the project's earliest
// scaffold, but never actually loaded anywhere (no next/font, no <link>) —
// every page has been silently falling back to the OS default sans/mono
// this whole time. next/font self-hosts the files (no external request,
// no layout shift) and exposes them as CSS variables Tailwind reads.
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

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
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
