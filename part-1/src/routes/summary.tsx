import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Share2, Calendar } from "lucide-react";
import { PatientShell } from "@/components/PatientShell";
import { api, PATIENT_ID } from "@/lib/api";

export const Route = createFileRoute("/summary")({
  head: () => ({
    meta: [
      { title: "Visit Summary — Cadence" },
      { name: "description", content: "What to bring to your next appointment." },
    ],
  }),
  component: SummaryPage,
});

type VisitSummary = {
  patient_id: string;
  generated_at: string;
  period_start: string;
  period_end: string;
  patient_facing: string;
  clinician_facing: string;
  conversation_starters: string[];
  key_metrics: Record<string, string>;
};

type SummaryResponse = {
  patient_id: string;
  visit_summary: VisitSummary;
};

function formatPeriod(start: string, end: string) {
  const s = new Date(start);
  const e = new Date(end);
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  return `${s.toLocaleDateString("en-US", opts)} – ${e.toLocaleDateString("en-US", opts)}`;
}

function SummaryPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["summary", PATIENT_ID],
    queryFn: () => api.get<SummaryResponse>("/patient/summary"),
  });

  const vs = data?.visit_summary;
  const metrics = vs ? Object.entries(vs.key_metrics) : [];

  return (
    <PatientShell eyebrow="Take to your visit" title="Your pre-visit brief">
      {/* Period header */}
      <section className="bg-leaf-800 text-white rounded-[28px] p-6 relative overflow-hidden mb-6">
        <div className="absolute -right-8 -bottom-12 size-40 bg-leaf-700/60 rounded-full blur-3xl" />
        <div className="relative">
          <div className="flex items-center gap-2 mb-3">
            <Calendar className="size-4 text-bloom-400" />
            <span className="text-[12px] font-semibold uppercase tracking-widest text-white/70">
              Monitoring period
            </span>
          </div>
          {isLoading ? (
            <div className="animate-pulse space-y-2">
              <div className="h-6 bg-white/10 rounded w-48" />
              <div className="h-4 bg-white/10 rounded w-32 mt-1" />
            </div>
          ) : vs ? (
            <>
              <p className="font-serif text-2xl leading-tight mb-1">{formatPeriod(vs.period_start, vs.period_end)}</p>
              <p className="text-white/70 text-[13px]">Ready for Dr. Reyes</p>
            </>
          ) : (
            <p className="font-serif text-2xl leading-tight mb-1">Your summary</p>
          )}
        </div>
      </section>

      {isLoading && (
        <div className="space-y-5">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-white border border-sand-100 rounded-2xl p-5 animate-pulse space-y-2">
              <div className="h-3 bg-sand-100 rounded w-1/4" />
              <div className="h-4 bg-sand-100 rounded w-full" />
              <div className="h-4 bg-sand-100 rounded w-4/5" />
            </div>
          ))}
        </div>
      )}

      {isError && (
        <p className="text-[14px] text-ink-muted text-center py-8">
          Couldn't load your summary right now. Try again in a moment.
        </p>
      )}

      {vs && (
        <div className="space-y-5">
          <Block label="What Cadence noticed">
            <p>{vs.patient_facing}</p>
          </Block>

          {metrics.length > 0 && (
            <Block label="Key metrics">
              <ul className="space-y-1.5">
                {metrics.map(([key, value]) => (
                  <Bullet key={key}>
                    <span className="font-medium capitalize">{key.replace(/_/g, " ")}</span>: {value}
                  </Bullet>
                ))}
              </ul>
            </Block>
          )}

          {vs.conversation_starters.length > 0 && (
            <Block label="Questions to ask Dr. Reyes">
              <ul className="space-y-1.5">
                {vs.conversation_starters.map((q) => (
                  <Bullet key={q}>{q}</Bullet>
                ))}
              </ul>
            </Block>
          )}
        </div>
      )}

      {vs && (
        <>
          <button className="mt-7 w-full bg-bloom-500 hover:bg-bloom-600 text-white font-semibold py-4 rounded-2xl shadow-lg shadow-bloom-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2">
            <Share2 className="size-4" />
            Share this brief with my doctor
          </button>
          <p className="text-center text-[11px] text-ink-muted mt-3">
            A copy is already in Dr. Reyes' inbox.
          </p>
        </>
      )}
    </PatientShell>
  );
}

function Block({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-sand-100 rounded-2xl p-5">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-bloom-600 mb-2">
        {label}
      </p>
      <div className="text-[14px] text-ink leading-relaxed font-serif">{children}</div>
    </div>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex gap-2.5">
      <span className="mt-2 size-1.5 rounded-full bg-leaf-700 shrink-0" />
      <span>{children}</span>
    </li>
  );
}
