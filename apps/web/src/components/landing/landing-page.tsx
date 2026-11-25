import {
  ArrowRight,
  BookOpenCheck,
  Boxes,
  CalendarClock,
  Database,
  Eye,
  FileSearch,
  Gauge as GaugeIcon,
  Lock,
  MessageSquareText,
  PlugZap,
  ScrollText,
  ShieldCheck,
  Truck,
  Workflow,
} from "lucide-react";
import Link from "next/link";

import { DemoRequestForm } from "@/components/landing/demo-request-form";
import { HeroDemo } from "@/components/landing/hero-demo";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { BrandLogo } from "@/components/ui/brand-logo";
import { buttonClass } from "@/components/ui/button";
import { Gauge } from "@/components/viz/gauge";
import { HeatCalendar } from "@/components/viz/heat-calendar";
import { SAMPLE_CALENDAR, SAMPLE_TIMELINE } from "@/components/viz/samples";
import { Timeline } from "@/components/viz/timeline";

const PROOF = [
  { icon: Eye, text: "Read-only by design" },
  { icon: FileSearch, text: "Every number traceable to its source" },
  { icon: Lock, text: "The AI never writes SQL" },
  { icon: ShieldCheck, text: "Roles and warehouses enforced on the server" },
];

const PROBLEMS = [
  {
    icon: Boxes,
    title: "Cash sits on the shelf",
    body: "Dormant and excess stock hide inside thousands of lines. Lumiant ranks it by value and age so you know what to clear first.",
  },
  {
    icon: Truck,
    title: "Orders slip without warning",
    body: "A missing component surfaces only when the customer calls. Lumiant shows which orders are at risk and the options to keep the promise.",
  },
  {
    icon: ScrollText,
    title: "Nobody trusts the numbers",
    body: "Spreadsheets disagree with the ERP. Every Lumiant figure shows its dataset, filters and rule version, and the AI cannot invent one.",
  },
];

const TRUST = [
  { icon: PlugZap, title: "Read-only connection", body: "Lumiant reads your warehouse or ERP extract. It never posts, edits or writes back." },
  { icon: ShieldCheck, title: "Scope on every query", body: "Warehouse and cost permissions are injected by the server into every query, including the assistant's." },
  { icon: Lock, title: "No AI-written SQL", body: "The model chooses typed analyses; validated, parameterised queries do the work." },
  { icon: BookOpenCheck, title: "Checked answers", body: "Every number in an AI answer must exist in the query results, or the answer is withheld." },
  { icon: Database, title: "Your data, your region", body: "External AI is off until your organisation approves a provider; built-in matching works without it." },
  { icon: FileSearch, title: "Full audit trail", body: "Every query, tool call and disclosure is recorded with the user, time and outcome." },
];

const FAQ = [
  {
    q: "Which systems does Lumiant work with?",
    a: "Lumiant maps your data onto one canonical inventory model. It reads SQL data warehouses and SAP list exports today, and it understands SAP, Odoo and Oracle terms in questions.",
  },
  {
    q: "Does the AI see our data?",
    a: "Only when your organisation approves an AI provider, and then only the question and a capped summary of the results it asked for. Without approval the assistant runs on built-in matching.",
  },
  {
    q: "Can the AI make up a number?",
    a: "No. The AI picks analyses; the platform runs them. A sentence with a figure that is not in the results is never shown.",
  },
  {
    q: "How long does it take to start?",
    a: "Mapping your fields to the canonical model is configuration, not code. A read-only connection and a mapping review are the first steps.",
  },
];

function Section({ id, eyebrow, title, intro, children }: { id?: string; eyebrow: string; title: string; intro?: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mx-auto max-w-6xl scroll-mt-24 px-5 py-20 sm:py-24">
      <p className="eyebrow text-accent">{eyebrow}</p>
      <h2 className="mt-3 max-w-3xl text-[2rem] leading-tight font-semibold tracking-tight text-ink sm:text-display">{title}</h2>
      {intro && <p className="mt-4 max-w-2xl text-base leading-relaxed text-ink-2">{intro}</p>}
      <div className="mt-12">{children}</div>
    </section>
  );
}

function Feature({ icon: Icon, title, body, bullets, visual, flip }: { icon: typeof Boxes; title: string; body: string; bullets: string[]; visual: React.ReactNode; flip?: boolean }) {
  return (
    <div className="grid items-center gap-10 lg:grid-cols-2">
      <div className={flip ? "min-w-0 lg:order-2" : "min-w-0"}>
        <span className="grid size-10 place-items-center rounded-control border border-line-strong bg-surface-2 text-accent">
          <Icon className="size-5" aria-hidden />
        </span>
        <h3 className="mt-4 text-section font-semibold text-ink">{title}</h3>
        <p className="mt-2 leading-relaxed text-ink-2">{body}</p>
        <ul className="mt-4 space-y-2">
          {bullets.map((b) => (
            <li key={b} className="flex gap-2 text-sm text-ink-2">
              <ArrowRight className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
              {b}
            </li>
          ))}
        </ul>
      </div>
      <div className={flip ? "min-w-0 lg:order-1" : "min-w-0"}>
        <div className="panel p-4 shadow-e2 sm:p-5">
          <p className="mb-3 flex items-center justify-between text-caption text-ink-3">
            <span>{title}</span>
            <span className="rounded-full border border-signal/35 bg-signal-soft px-2 py-0.5 font-medium text-signal">Sample data</span>
          </p>
          {visual}
        </div>
      </div>
    </div>
  );
}

/** The public landing page. Static content and sample visuals only: no API call, no tenant data. */
export function LandingPage({ signInHref }: { signInHref: string }) {
  return (
    <div className="min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[70] focus:rounded-control focus:bg-surface-3 focus:px-3 focus:py-2 focus:text-sm">
        Skip to content
      </a>
      <header className="glass sticky top-0 z-[40] border-b border-glass-line">
        <nav aria-label="Site" className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-5">
          <Link href="/" aria-label="Lumiant home">
            <BrandLogo height={34} />
          </Link>
          <ul className="hidden items-center gap-6 text-sm text-ink-2 md:flex">
            <li>
              <a className="hover:text-ink" href="#product">
                Product
              </a>
            </li>
            <li>
              <a className="hover:text-ink" href="#how">
                How it works
              </a>
            </li>
            <li>
              <a className="hover:text-ink" href="#security">
                Security
              </a>
            </li>
            <li>
              <a className="hover:text-ink" href="#faq">
                FAQ
              </a>
            </li>
          </ul>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <Link href={signInHref} className={buttonClass({ variant: "ghost" })} data-testid="landing-sign-in">
              Sign in
            </Link>
            <a href="#demo" className={buttonClass({ variant: "primary", className: "hidden sm:inline-flex" })}>
              Request a demo
            </a>
          </div>
        </nav>
      </header>

      <main id="main">
        <section className="relative overflow-hidden">
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 pt-16 pb-20 lg:grid-cols-[1.05fr_1fr] lg:pt-24">
            <div className="rise min-w-0">
              <p className="inline-flex items-center rounded-full border border-line-strong bg-surface px-3 py-1 text-caption font-medium text-ink-2">Inventory intelligence with an analyst you can check
              </p>
              <h1 className="mt-6 text-[2.5rem] leading-[1.05] font-semibold tracking-tight text-ink sm:text-hero">
                Know every unit, every cost, every risk, <span className="text-accent">and ask why.</span>
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-2">
                Lumiant connects read-only to your ERP data, turns it into one trusted inventory model, and answers in plain language, with the source of every number.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <a href="#demo" className={buttonClass({ variant: "primary", size: "lg" })}>
                  Request a demo <ArrowRight className="size-4" aria-hidden />
                </a>
                <Link href={signInHref} className={buttonClass({ size: "lg" })}>
                  Open the demo workspace
                </Link>
              </div>
              <p className="mt-4 text-caption text-ink-3">The demo workspace runs on generated data, labelled SYNTHETIC on every screen.</p>
            </div>
            <div className="rise min-w-0" style={{ animationDelay: "120ms" }}>
              <HeroDemo />
            </div>
          </div>
        </section>

        <section aria-label="Principles" className="border-y border-line bg-surface/60">
          <ul className="mx-auto grid max-w-6xl gap-4 px-5 py-6 sm:grid-cols-2 lg:grid-cols-4">
            {PROOF.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-2.5 text-sm text-ink-2">
                <Icon className="size-4 shrink-0 text-accent" aria-hidden /> {text}
              </li>
            ))}
          </ul>
        </section>

        <Section eyebrow="Why Lumiant" title="Inventory problems are expensive because they are invisible.">
          <div className="grid gap-4 md:grid-cols-3">
            {PROBLEMS.map(({ icon: Icon, title, body }) => (
              <div key={title} className="panel p-6">
                <Icon className="size-5 text-accent" aria-hidden />
                <h3 className="mt-4 text-title font-semibold text-ink">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-2">{body}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section id="product" eyebrow="Product" title="One place to see, ask and act." intro="Dashboards for the daily picture, an analyst for the questions behind it, and planning views that turn risk into options.">
          <div className="space-y-24">
            <Feature
              icon={GaugeIcon}
              title="Command centre"
              body="Value, risk and data health on one screen, ranked by what needs attention. Every tile opens the rows behind it."
              bullets={["Value by warehouse, group, ABC class and stage", "Expiring lots, dormant and excess stock", "Data-quality checks that name the missing field"]}
              visual={
                <div className="grid items-center gap-4 sm:grid-cols-[auto_1fr]">
                  <Gauge value={92} exact="92" status="Good" label="Data quality score" size={148} />
                  <HeatCalendar days={SAMPLE_CALENDAR.slice(0, 98)} unitLabel="Lots expiring" label="Sample lots expiring per day" />
                </div>
              }
            />
            <Feature
              flip
              icon={MessageSquareText}
              title="Lumiant Analyst"
              body="Ask in your own words or in your ERP's terms, in English or Arabic. The Analyst plans the analyses, shows its work and cites its definitions."
              bullets={["Chains analyses: find the item, then check its stock and cost", "Every figure traced to the query that produced it", "Definitions and methods answered with citations"]}
              visual={
                <div className="space-y-2.5 text-sm">
                  <div className="ml-auto w-fit rounded-panel rounded-br-sm bg-accent px-3 py-2 text-accent-ink">How is dormant stock defined?</div>
                  <div className="rounded-panel border border-line bg-surface-2 p-3 text-ink">
                    Stock on hand with no issue movement within the chosen window before the data date. Receipts and transfers do not count as movement.
                    <p className="mt-2 flex items-center gap-1.5 text-caption text-ink-3">
                      <BookOpenCheck className="size-3.5 text-accent" aria-hidden /> Inventory metrics · Dormant or slow-moving stock
                    </p>
                  </div>
                </div>
              }
            />
            <Feature
              icon={CalendarClock}
              title="Planning and commitment protection"
              body="See which customer orders are at risk, why, and the options to keep the promise: a transfer, an approved alternate, a faster supplier."
              bullets={["Time-phased requirements from bills of materials", "Supplier comparison that puts delivery first", "Recommendations only: nothing is posted to your ERP"]}
              visual={<Timeline lanes={SAMPLE_TIMELINE.lanes} from={SAMPLE_TIMELINE.from} to={SAMPLE_TIMELINE.to} today={SAMPLE_TIMELINE.today} label="Sample customer orders with supply plans and due dates" />}
            />
          </div>
        </Section>

        <Section id="how" eyebrow="How it works" title="Connected in days, not a re-implementation.">
          <ol className="grid gap-4 md:grid-cols-3">
            {[
              { icon: PlugZap, title: "Connect", body: "A read-only connection to your warehouse, or a governed import of ERP list exports." },
              { icon: Workflow, title: "Model", body: "Your fields map onto one canonical inventory model, validated before any screen uses it." },
              { icon: MessageSquareText, title: "Ask and act", body: "Dashboards, reports and the Analyst all run on the same secured query engine." },
            ].map(({ icon: Icon, title, body }, i) => (
              <li key={title} className="panel relative p-6">
                <span className="figure absolute top-5 right-5 text-caption text-ink-3">0{i + 1}</span>
                <Icon className="size-5 text-accent" aria-hidden />
                <h3 className="mt-4 text-title font-semibold text-ink">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-2">{body}</p>
              </li>
            ))}
          </ol>
        </Section>

        <Section id="security" eyebrow="Trust and security" title="Built so you can check it." intro="Security lives in application code, not in a prompt. The AI is a planner and a writer, never a source of figures.">
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {TRUST.map(({ icon: Icon, title, body }) => (
              <li key={title} className="rounded-panel border border-line p-5">
                <Icon className="size-5 text-accent" aria-hidden />
                <h3 className="mt-3 text-sm font-semibold text-ink">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{body}</p>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="faq" eyebrow="FAQ" title="Questions we hear first.">
          <div className="max-w-3xl divide-y divide-line rounded-panel border border-line">
            {FAQ.map(({ q, a }) => (
              <details key={q} className="group px-5 py-4">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-ink">
                  {q}
                  <span className="text-ink-3 transition-transform group-open:rotate-45" aria-hidden>
                    +
                  </span>
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-ink-2">{a}</p>
              </details>
            ))}
          </div>
        </Section>

        <section id="demo" className="scroll-mt-24 px-5 pb-24">
          <div className="mx-auto grid max-w-6xl gap-10 rounded-[1.25rem] border border-line-strong bg-surface p-8 shadow-e2 sm:p-12 lg:grid-cols-2">
            <div>
              <p className="eyebrow text-accent">Request a demo</p>
              <h2 className="mt-3 text-[2rem] leading-tight font-semibold tracking-tight text-ink">See Lumiant on data like yours.</h2>
              <p className="mt-4 leading-relaxed text-ink-2">
                Tell us a little about your inventory and systems. We use these details only to arrange the demo.
              </p>
            </div>
            <DemoRequestForm />
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-8 text-caption text-ink-3">
          <BrandLogo height={26} />
          <p>© 2026 Lumiant Group. Inventory intelligence platform.</p>
          <Link href={signInHref} className="hover:text-ink">
            Sign in
          </Link>
        </div>
      </footer>
    </div>
  );
}
