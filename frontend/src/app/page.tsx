import Link from "next/link";
import { Sparkles, Radar, MessageCircle, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const FEATURES = [
  {
    icon: Radar,
    title: "Explainable AI evaluation",
    body: "Three sequential agents ground every score in static analysis and evidence — never a raw model opinion.",
  },
  {
    icon: ShieldCheck,
    title: "Evidence-backed scorecards",
    body: "Every criterion traces back to specific findings you can inspect. \"Good code quality\" is never the whole story.",
  },
  {
    icon: MessageCircle,
    title: "AI mentor chatbot",
    body: "Ask why you scored what you scored, and get concrete, encouraging guidance grounded in your own repository.",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto flex max-w-5xl flex-col items-center px-6 pb-24 pt-28 text-center sm:pt-36">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-4 py-1.5 text-xs font-medium text-accent">
          <Sparkles className="h-3.5 w-3.5" />
          AI-native hackathon judging
        </div>
        <h1 className="text-5xl font-bold tracking-tight text-white sm:text-6xl">
          EVAL<span className="text-accent">ON</span>
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-gray-400">
          Submit a repo. Get a scorecard you can actually trust — every number traces to specific,
          observed evidence, and a mentor is on hand to explain it.
        </p>
        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
          <Button asChild size="lg">
            <Link href="/auth/register">Join as a participant</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/auth/login">Admin sign in</Link>
          </Button>
        </div>
      </div>

      <div className="mx-auto grid max-w-5xl gap-6 px-6 pb-28 sm:grid-cols-3">
        {FEATURES.map((feature) => (
          <Card key={feature.title} className="border-white/10 bg-card-elevated/50">
            <CardContent className="pt-6">
              <feature.icon className="mb-4 h-6 w-6 text-accent" />
              <h3 className="mb-2 font-semibold text-white">{feature.title}</h3>
              <p className="text-sm text-gray-400">{feature.body}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
