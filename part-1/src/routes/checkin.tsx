import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Check } from "lucide-react";
import { toast } from "sonner";
import { PatientShell } from "@/components/PatientShell";
import { DailyCheckin, type Checkin } from "@/components/DailyCheckin";
import { api, PATIENT_ID } from "@/lib/api";

export const Route = createFileRoute("/checkin")({
  head: () => ({
    meta: [
      { title: "Check-in — Cadence" },
      { name: "description", content: "Log today's readings for your care team." },
    ],
  }),
  component: CheckinPage,
});

function CheckinPage() {
  // Each task logs through the agent so red flags still route to Dr. Reyes,
  // but routine logging stays quiet — we only surface a banner if flagged.
  const [sessionId] = useState(() =>
    typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `s-${Date.now()}`,
  );
  const [checkin, setCheckin] = useState<Checkin>({});
  const [sending, setSending] = useState(false);
  const [flagged, setFlagged] = useState(false);

  async function logTask(message: string, patch: Checkin) {
    if (sending) return;
    setSending(true);
    try {
      const res = await api.post<{ reply: string; flagged: boolean }>("/chat/message", {
        patient_id: PATIENT_ID,
        message,
        session_id: sessionId,
      });
      setCheckin((c) => ({ ...c, ...patch }));
      if (res.flagged) setFlagged(true);
    } catch {
      toast.error("Couldn't save that — please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <PatientShell eyebrow="Daily Check-in" title="Today">
      <DailyCheckin checkin={checkin} busy={sending} onLog={logTask} />

      {flagged && (
        <div className="mt-5 px-4 py-3 rounded-2xl bg-bloom-500/[0.08] border border-bloom-500/25 flex items-start gap-3">
          <div className="size-7 rounded-full bg-bloom-500/15 grid place-items-center shrink-0 mt-0.5">
            <Check className="size-3.5 text-bloom-600" strokeWidth={3} />
          </div>
          <div className="text-[13px] leading-snug">
            <p className="font-semibold text-leaf-800">Sent to Dr. Reyes</p>
            <p className="text-ink-muted">
              One of today's readings is above your care-plan threshold. Your care team has the full
              picture — no action needed from you.
            </p>
          </div>
        </div>
      )}

      <p className="mt-6 text-center text-[12px] text-ink/40 leading-relaxed px-4">
        Your readings go straight to your care team. If anything needs attention, Cade will let you
        know.
      </p>
    </PatientShell>
  );
}
