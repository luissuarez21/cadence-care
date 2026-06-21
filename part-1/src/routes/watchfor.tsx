import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Eye,
  Activity,
  Droplets,
  Brain,
  Footprints,
  Zap,
  Pill,
  Scale,
  AlertCircle,
  type LucideIcon,
} from "lucide-react";
import { PatientShell } from "@/components/PatientShell";
import { api, PATIENT_ID } from "@/lib/api";

export const Route = createFileRoute("/watchfor")({
  head: () => ({
    meta: [
      { title: "Things to Watch For — Cadence" },
      { name: "description", content: "What to let Cadence know about right away." },
    ],
  }),
  component: WatchForPage,
});

type RedFlag = {
  description: string;
  severity: "ok" | "monitor" | "escalate" | "escalate_urgent";
  escalation_message: string;
};

type WatchForResponse = {
  patient_id: string;
  red_flags: RedFlag[];
};

function pickIcon(description: string): LucideIcon {
  const d = description.toLowerCase();
  if (d.includes("vision") || d.includes("visual") || d.includes("blurred") || d.includes("spots") || d.includes("flashing")) return Eye;
  if (d.includes("headache") || d.includes("head")) return Brain;
  if (d.includes("bp") || d.includes("blood pressure") || d.includes("systolic") || d.includes("diastolic")) return Activity;
  if (d.includes("swelling") || d.includes("facial") || d.includes("edema") || d.includes("hand")) return Droplets;
  if (d.includes("fetal") || d.includes("movement") || d.includes("kick")) return Footprints;
  if (d.includes("contraction") || d.includes("preterm") || d.includes("labor") || d.includes("gestation")) return Zap;
  if (d.includes("aspirin") || d.includes("medication") || d.includes("dose")) return Pill;
  if (d.includes("weight") || d.includes("gain")) return Scale;
  return AlertCircle;
}

function WatchForPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["watchfor", PATIENT_ID],
    queryFn: () => api.get<WatchForResponse>("/patient/watchfor"),
  });

  return (
    <PatientShell eyebrow="From your care plan" title="Things to watch for">
      <p className="text-[14px] text-ink-muted leading-relaxed mb-6 font-serif">
        These come straight from your visit with Dr. Reyes. None of them mean
        something is wrong — they're just the things to let me know about right away.
      </p>

      {isLoading && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="bg-white p-4 rounded-2xl border border-sand-100 flex items-start gap-4 animate-pulse">
              <div className="size-11 rounded-xl bg-sand-100 shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3.5 bg-sand-100 rounded w-2/5" />
                <div className="h-3 bg-sand-100 rounded w-4/5" />
              </div>
            </div>
          ))}
        </div>
      )}

      {isError && (
        <p className="text-[14px] text-ink-muted text-center py-8">
          Couldn't load your care plan right now. Try again in a moment.
        </p>
      )}

      {data && (
        <div className="space-y-3">
          {data.red_flags.map((flag) => (
            <Card key={flag.description} flag={flag} />
          ))}
        </div>
      )}

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

function Card({ flag }: { flag: RedFlag }) {
  const Icon = pickIcon(flag.description);
  const urgent = flag.severity === "escalate" || flag.severity === "escalate_urgent";
  const iconBg = urgent ? "bg-bloom-500/12 text-bloom-600" : "bg-leaf-700/10 text-leaf-700";

  return (
    <div className="bg-white p-4 rounded-2xl border border-sand-100 flex items-start gap-4">
      <div className={`size-11 rounded-xl grid place-items-center shrink-0 ${iconBg}`}>
        <Icon className="size-5" strokeWidth={2} />
      </div>
      <div>
        <p className="font-semibold text-[14px] text-leaf-800 mb-0.5">{flag.description}</p>
        <p className="text-[13px] text-ink-muted leading-relaxed">{flag.escalation_message}</p>
      </div>
    </div>
  );
}
