import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
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

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatDay(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString("en-US", { weekday: "short" });
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

function HistoryPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["history", PATIENT_ID],
    queryFn: () => api.get<HistoryResponse>("/patient/history"),
  });

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
              <span className="font-serif text-4xl font-semibold text-leaf-800">{data.check_in_count}</span>
              <span className="text-[13px] text-ink-muted">check-ins logged</span>
            </div>
            {data.flags_count > 0 && (
              <div className="flex items-center gap-2 mt-3">
                <div className="size-6 rounded-full bg-leaf-700/15 grid place-items-center">
                  <Check className="size-3 text-leaf-700" strokeWidth={3} />
                </div>
                <p className="text-[13px] text-leaf-800 font-medium">
                  {data.flags_count === 1 ? "One pattern flagged" : `${data.flags_count} patterns flagged`}. Dr. Reyes has been notified.
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
            {data.entries.map((entry) => {
              const flagged = isEscalated(entry);
              return (
                <div key={entry.timestamp} className="relative pl-9">
                  <div
                    className={
                      "absolute left-0 top-1.5 size-[22px] rounded-full grid place-items-center " +
                      (flagged ? "bg-bloom-500" : "bg-white border-2 border-sand-200")
                    }
                  >
                    {flagged && <span className="size-1.5 rounded-full bg-white" />}
                  </div>
                  <div className="bg-white border border-sand-100 rounded-2xl p-4">
                    <div className="flex justify-between items-baseline mb-1.5">
                      <span className="font-semibold text-[14px] text-leaf-800">
                        {formatDay(entry.timestamp)}{" "}
                        <span className="text-ink/40 font-normal">· {formatDate(entry.timestamp)}</span>
                      </span>
                      <span className="font-serif text-[15px] text-ink">{formatBp(entry)}</span>
                    </div>
                    <p className="text-[13px] text-ink-muted leading-snug">
                      {entry.notes || entry.raw_text || "Check-in recorded"}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </PatientShell>
  );
}
