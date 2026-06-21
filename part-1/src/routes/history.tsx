import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Check, HeartPulse, AlertTriangle, Eye, Droplets, Baby, Pill, ChevronDown } from "lucide-react";
import { PatientShell } from "@/components/PatientShell";
import { api, PATIENT_ID } from "@/lib/api";

export const Route = createFileRoute("/history")({
  head: () => ({
    meta: [
      { title: "History — Cadence" },
      { name: "description", content: "Your check-in history." },
    ],
  }),
  component: HistoryPage,
});

type SymptomLog = {
  patient_id: string;
  timestamp: string;
  bp_systolic?: number | null;
  bp_diastolic?: number | null;
  headache_severity?: number | null;
  swelling_location?: string | null;
  vision_changes?: boolean | null;
  fetal_movement?: string | null;
  medication_taken?: boolean | null;
  raw_text: string;
  notes: string;
};

type HistoryResponse = {
  patient_id: string;
  entries: SymptomLog[];
  check_in_count: number;
  flags_count: number;
};

const MAX_PER_DAY = 2;
const MAX_DAYS = 6;

function dayKey(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function formatDay(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const a = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const b = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diff = Math.round((b.getTime() - a.getTime()) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString("en-US", { weekday: "long" });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function formatBp(log: SymptomLog): string {
  if (log.bp_systolic != null && log.bp_diastolic != null) {
    return `${log.bp_systolic} / ${log.bp_diastolic}`;
  }
  return "—";
}

function isEscalated(log: SymptomLog): boolean {
  if (log.bp_systolic != null && log.bp_diastolic != null) {
    return log.bp_systolic >= 140 || log.bp_diastolic >= 90;
  }
  return false;
}

// Newest first, at most 2 readings per calendar day, most recent 6 days only.
function buildTimeline(entries: SymptomLog[]): SymptomLog[] {
  const sorted = [...entries].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );
  const perDay = new Map<string, SymptomLog[]>();
  for (const e of sorted) {
    const key = dayKey(e.timestamp);
    const arr = perDay.get(key) ?? [];
    if (arr.length < MAX_PER_DAY) arr.push(e);
    perDay.set(key, arr);
  }
  return [...perDay.keys()].slice(0, MAX_DAYS).flatMap((k) => perDay.get(k)!);
}

function HistoryPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["history", PATIENT_ID],
    queryFn: () => api.get<HistoryResponse>("/patient/history"),
  });
  const [openKey, setOpenKey] = useState<string | null>(null);

  const timeline = data ? buildTimeline(data.entries) : [];
  const checkInCount = timeline.length;
  const flagsCount = timeline.filter(isEscalated).length;

  return (
    <PatientShell eyebrow="Your check-ins" title="A gentle log">
      <section className="bg-sand-100 rounded-[28px] p-5 mb-6 border border-black/[0.04]">
        {isLoading ? (
          <div className="animate-pulse space-y-2">
            <div className="h-9 bg-white/60 rounded w-24" />
            <div className="h-4 bg-white/60 rounded w-40 mt-1" />
          </div>
        ) : data ? (
          <>
            <div className="flex items-baseline gap-3 mb-1">
              <span className="font-serif text-4xl font-semibold text-leaf-800">{checkInCount}</span>
              <span className="text-[13px] text-ink-muted">check-ins logged</span>
            </div>
            {flagsCount > 0 && (
              <div className="flex items-center gap-2 mt-3">
                <div className="size-6 rounded-full bg-bloom-500/15 grid place-items-center">
                  <Check className="size-3 text-bloom-600" strokeWidth={3} />
                </div>
                <p className="text-[13px] text-leaf-800 font-medium">
                  {flagsCount === 1 ? "One reading flagged" : `${flagsCount} readings flagged`}. Dr.
                  Reyes has been notified.
                </p>
              </div>
            )}
          </>
        ) : null}
      </section>

      <h3 className="text-[11px] font-semibold text-ink-muted uppercase tracking-widest mb-4 px-1">
        Timeline
      </h3>

      {isLoading && (
        <div className="relative">
          <div className="absolute left-[11px] top-2 bottom-2 w-px bg-sand-200" />
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="relative pl-9">
                <div className="absolute left-0 top-1.5 size-[22px] rounded-full bg-sand-100 animate-pulse" />
                <div className="bg-white border border-sand-100 rounded-2xl p-4 animate-pulse space-y-2">
                  <div className="h-3.5 bg-sand-100 rounded w-1/3" />
                  <div className="h-3 bg-sand-100 rounded w-2/3" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {isError && (
        <p className="text-[14px] text-ink-muted text-center py-8">
          Couldn't load your history right now. Try again in a moment.
        </p>
      )}

      {data && (
        <div className="relative">
          <div className="absolute left-[11px] top-2 bottom-2 w-px bg-sand-200" />
          <div className="space-y-4">
            {timeline.map((entry) => {
              const flagged = isEscalated(entry);
              const open = openKey === entry.timestamp;
              return (
                <div key={entry.timestamp} className="relative pl-9">
                  <div
                    className={
                      "absolute left-0 top-1.5 size-[22px] rounded-full grid place-items-center text-white " +
                      (flagged ? "bg-bloom-600 ring-2 ring-bloom-500/25" : "bg-bloom-500")
                    }
                  >
                    {flagged ? (
                      <span className="size-1.5 rounded-full bg-white" />
                    ) : (
                      <Check className="size-3" strokeWidth={3} />
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => setOpenKey(open ? null : entry.timestamp)}
                    className="w-full text-left bg-white border border-sand-100 rounded-2xl p-4 hover:border-bloom-500/30 transition-colors"
                  >
                    <div className="flex justify-between items-baseline mb-1.5">
                      <span className="font-semibold text-[14px] text-leaf-800">
                        {formatDay(entry.timestamp)}{" "}
                        <span className="text-ink/40 font-normal">· {formatTime(entry.timestamp)}</span>
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className="font-serif text-[15px] text-ink">{formatBp(entry)}</span>
                        <ChevronDown
                          className={"size-4 text-ink/30 transition-transform " + (open ? "rotate-180" : "")}
                        />
                      </span>
                    </div>
                    <p className="text-[13px] text-ink-muted leading-snug">
                      {entry.notes || entry.raw_text || "Check-in recorded"}
                    </p>

                    {open && <LoggedDetail log={entry} />}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </PatientShell>
  );
}

function LoggedDetail({ log }: { log: SymptomLog }) {
  const rows: { icon: typeof HeartPulse; label: string; value: string }[] = [];
  if (log.bp_systolic != null && log.bp_diastolic != null) {
    rows.push({ icon: HeartPulse, label: "Blood pressure", value: `${log.bp_systolic} / ${log.bp_diastolic}` });
  }
  if (log.headache_severity != null) {
    rows.push({ icon: AlertTriangle, label: "Headache", value: `${log.headache_severity}/10` });
  }
  if (log.vision_changes) {
    rows.push({ icon: Eye, label: "Vision changes", value: "Reported" });
  }
  if (log.swelling_location) {
    rows.push({ icon: Droplets, label: "Swelling", value: log.swelling_location });
  }
  if (log.fetal_movement) {
    rows.push({ icon: Baby, label: "Baby's movement", value: log.fetal_movement });
  }
  if (log.medication_taken != null) {
    rows.push({ icon: Pill, label: "Low-dose aspirin", value: log.medication_taken ? "Taken" : "Not taken" });
  }

  return (
    <div className="mt-3 pt-3 border-t border-sand-100 space-y-1.5" onClick={(e) => e.stopPropagation()}>
      <p className="text-[11px] font-semibold text-ink/40 uppercase tracking-wider mb-1">What you logged</p>
      {rows.length > 0 ? (
        rows.map((r) => {
          const Icon = r.icon;
          return (
            <div key={r.label} className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-sand-100/70">
              <div className="size-7 rounded-full bg-bloom-500/12 text-bloom-600 grid place-items-center shrink-0">
                <Icon className="size-3.5" />
              </div>
              <span className="flex-1 text-[13px] text-leaf-800">{r.label}</span>
              <span className="text-[13px] font-semibold text-leaf-800">{r.value}</span>
            </div>
          );
        })
      ) : (
        <p className="text-[13px] text-ink-muted">{log.raw_text || "Check-in recorded."}</p>
      )}
    </div>
  );
}
