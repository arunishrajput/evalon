import Link from "next/link";
import { Activity, MessageCircle, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { HeroRadarPreview } from "@/components/landing/HeroRadarPreview";

const PIPELINE = [
  {
    step: "01",
    title: "Measure",
    body: "radon, semgrep, and doc-coverage tools run against the cloned repo first — complexity, security findings, test presence — before a single AI token is generated.",
  },
  {
    step: "02",
    title: "Ground",
    body: "Three agents run one at a time, never in parallel: Repository Understanding, then Code Quality, then Innovation. Each reads the tool output directly — none of them guess.",
  },
  {
    step: "03",
    title: "Explain",
    body: "Every criterion ships with the specific evidence that produced it. Click any score on your scorecard to see exactly what the tools found.",
  },
];

const FEATURES = [
  {
    icon: Activity,
    title: "Watch a hackathon judge itself",
    body: "Submission counts, score distributions, and tech-stack trends update live over SSE as evaluations complete — no refresh, ever.",
  },
  {
    icon: MessageCircle,
    title: "A mentor that's read the evidence",
    body: "Ask why a score landed where it did. Answers cite the same static analysis and agent findings your scorecard is built on, never a generic tip.",
  },
  {
    icon: ShieldCheck,
    title: "Never a blank screen",
    body: "If a model is busy or a tool times out, EVALON falls back to static analysis and says so plainly — one failure never crashes an evaluation.",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <span className="text-lg font-bold tracking-tight text-white">
          EVAL<span className="text-accent">ON</span>
        </span>
        <Button asChild variant="ghost" size="sm">
          <Link href="/auth/login">Admin sign in</Link>
        </Button>
      </div>

      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.15]"
          style={{
            backgroundImage:
              "radial-gradient(circle, #ffffff 1px, transparent 1px)",
            backgroundSize: "28px 28px",
            maskImage: "radial-gradient(ellipse 60% 50% at 50% 20%, black, transparent)",
            WebkitMaskImage: "radial-gradient(ellipse 60% 50% at 50% 20%, black, transparent)",
          }}
        />
        <div className="relative mx-auto grid max-w-6xl gap-16 px-6 pb-24 pt-10 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:pb-32 lg:pt-16">
          <div>
            <p className="motion-safe:animate-fade-up font-mono text-xs uppercase tracking-[0.15em] text-accent">
              Tools measure. AI explains.
            </p>
            <h1 className="motion-safe:animate-fade-up motion-safe:[animation-delay:100ms] mt-4 text-4xl font-bold leading-[1.1] tracking-tight text-white sm:text-5xl">
              Every score traces back to evidence you can click.
            </h1>
            <p className="motion-safe:animate-fade-up motion-safe:[animation-delay:200ms] mt-6 max-w-xl text-lg text-gray-400">
              Submit a repo. EVALON clones it, runs real static analysis, then grounds three
              sequential AI agents in what those tools actually found — so no score on your
              scorecard is a raw model opinion.
            </p>
            <div className="motion-safe:animate-fade-up motion-safe:[animation-delay:300ms] mt-9 flex flex-wrap items-center gap-x-8 gap-y-4">
              <Button asChild size="lg">
                <Link href="/auth/register">Join as a participant</Link>
              </Button>
              <a
                href="#how-it-works"
                className="text-sm font-medium text-gray-400 underline-offset-4 transition-colors hover:text-white hover:underline"
              >
                See how scoring works &darr;
              </a>
            </div>
            <p className="motion-safe:animate-fade-up motion-safe:[animation-delay:400ms] mt-8 font-mono text-xs text-gray-600">
              Runs on local models. Your code is never sent to a third-party API.
            </p>
          </div>

          <div className="flex justify-center lg:justify-end">
            <HeroRadarPreview />
          </div>
        </div>
      </section>

      <section id="how-it-works" className="border-t border-white/5 px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <p className="font-mono text-xs uppercase tracking-[0.15em] text-gray-500">The pipeline</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-bold tracking-tight text-white">
            Three tools run before a single AI token does.
          </h2>
          <div className="mt-14 grid gap-10 sm:grid-cols-3 sm:gap-8">
            {PIPELINE.map((item) => (
              <div key={item.step}>
                <span className="font-mono text-sm text-accent">{item.step}</span>
                <h3 className="mt-3 text-lg font-semibold text-white">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-gray-400">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-white/5 px-6 py-24">
        <div className="mx-auto grid max-w-6xl gap-6 sm:grid-cols-3">
          {FEATURES.map((feature) => (
            <Card key={feature.title} className="border-white/10 bg-card-elevated/50">
              <CardContent className="pt-6">
                <feature.icon className="mb-4 h-6 w-6 text-accent" aria-hidden />
                <h3 className="mb-2 font-semibold text-white">{feature.title}</h3>
                <p className="text-sm text-gray-400">{feature.body}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-t border-white/5 px-6 py-24">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-white">See your own repo&apos;s evidence.</h2>
          <p className="max-w-md text-gray-400">
            Submit your hackathon repo and get a scorecard where every number opens into the
            findings behind it.
          </p>
          <Button asChild size="lg">
            <Link href="/auth/register">Join as a participant</Link>
          </Button>
        </div>
      </section>

      <footer className="border-t border-white/5 px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 sm:flex-row">
          <span className="text-sm font-bold tracking-tight text-white">
            EVAL<span className="text-accent">ON</span>
          </span>
          <span className="font-mono text-xs text-gray-600">Tools measure. AI explains.</span>
        </div>
      </footer>
    </main>
  );
}
