import { createFileRoute } from "@tanstack/react-router";
import { Eye, Activity, Droplets, Brain, Footprints } from "lucide-react";
import { PatientShell } from "@/components/PatientShell";

export const Route = createFileRoute("/watchfor")({
  head: () => ({
    meta: [
      { title: "Things to Watch For — Cadence" },
      { name: "description", content: "What to let Cadence know about right away." },
    ],
  }),
  component: WatchForPage,
});

const items = [
  {
    icon: Eye,
    title: "Vision changes",
    body: "Any sudden blurring, double vision, or seeing spots.",
    tone: "bloom",
  },
  {
    icon: Brain,
    title: "Headaches that won't rest",
    body: "A headache that doesn't ease after water, food, and a quiet hour.",
    tone: "leaf",
  },
  {
    icon: Activity,
    title: "Blood pressure 140/90 or higher",
    body: "Two readings ten minutes apart. We'll guide you through it.",
    tone: "bloom",
  },
  {
    icon: Droplets,
    title: "Sudden swelling",
    body: "Especially in your face, hands, or around your eyes.",
    tone: "leaf",
  },
  {
    icon: Footprints,
    title: "Less movement from baby",
    body: "Fewer than 10 kicks in two hours when baby is usually active.",
    tone: "bloom",
  },
] as const;

function WatchForPage() {
  return (
    <PatientShell eyebrow="From your care plan" title="Things to watch for">
      <p className="text-[14px] text-ink-muted leading-relaxed mb-6 font-serif">
        These come straight from your visit with Dr. Reyes. None of them mean
        something is wrong — they're just the things to let me know about right away.
      </p>

      <div className="space-y-3">
        {items.map((item) => (
          <Card key={item.title} {...item} />
        ))}
      </div>

      <div className="mt-8 p-5 rounded-2xl bg-leaf-800 text-white relative overflow-hidden">
        <div className="absolute -right-10 -bottom-10 size-32 bg-leaf-700/60 rounded-full blur-3xl" />
        <p className="text-[11px] font-semibold uppercase tracking-widest text-white/60 mb-2">
          A note from Cadence
        </p>
        <p className="font-serif text-[16px] leading-snug relative">
          You don't need to memorize this list. I'll check in with you every day,
          and if anything matches, I'll know what to do.
        </p>
      </div>
    </PatientShell>
  );
}

function Card({
  icon: Icon,
  title,
  body,
  tone,
}: {
  icon: typeof Eye;
  title: string;
  body: string;
  tone: "bloom" | "leaf";
}) {
  const iconBg = tone === "bloom" ? "bg-bloom-500/12 text-bloom-600" : "bg-leaf-700/10 text-leaf-700";
  return (
    <div className="bg-white p-4 rounded-2xl border border-sand-100 flex items-start gap-4">
      <div className={`size-11 rounded-xl grid place-items-center shrink-0 ${iconBg}`}>
        <Icon className="size-5" strokeWidth={2} />
      </div>
      <div>
        <p className="font-semibold text-[14px] text-leaf-800 mb-0.5">{title}</p>
        <p className="text-[13px] text-ink-muted leading-relaxed">{body}</p>
      </div>
    </div>
  );
}
