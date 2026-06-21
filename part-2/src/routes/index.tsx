import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, CLINICIAN_ID } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Cadence · Clinician Dashboard" },
      {
        name: "description",
        content:
          "Cadence clinician dashboard — risk-ranked patient panel, between-visit timeline, pattern detection, and pre-visit briefings for high-risk pregnancy care.",
      },
      { property: "og:title", content: "Cadence · Clinician Dashboard" },
      {
        property: "og:description",
        content:
          "A complete picture of every high-risk pregnancy, before the appointment begins.",
      },
    ],
  }),
  component: ClinicianDashboard,
});

/* ── API contract types ───────────────────────────────────────────────────── */

type Severity = "ok" | "monitor" | "escalate" | "escalate_urgent";

interface PanelRow {
  patient_id: string;
  patient_name: string;
  severity: Severity;
  last_check_in: string | null;
  headline: string;
}

interface SymptomLog {
  patient_id: string;
  timestamp: string;
  bp_systolic: number | null;
  bp_diastolic: number | null;
  headache_severity: number | null;
  swelling_location: string | null;
  vision_changes: boolean | null;
  fetal_movement: string | null;
  medication_taken: boolean | null;
  raw_text: string | null;
  notes: string | null;
}

interface PatternAlert {
  patient_id: string;
  title: string;
  detail: string;
  metric: string;
  severity: Severity;
}

interface RiskScore {
  patient_id: string;
  timestamp: string;
  severity: Severity;
  rationale: string;
  recommended_action: string;
  triggered_flags: string[];
}

interface VisitSummary {
  patient_id: string;
  generated_at: string;
  period_start: string;
  period_end: string;
  patient_facing: string;
  clinician_facing: string;
  conversation_starters: string[];
  key_metrics: Record<string, string>;
}

interface PatientDetail {
  patient_id: string;
  patient_name: string;
  current_risk: RiskScore | null;
  timeline: SymptomLog[];
  patterns: PatternAlert[];
  visit_summary: VisitSummary | null;
}

interface EscalationSummary {
  escalation_id: string;
  patient_id: string;
  patient_name: string;
  timestamp: string;
  severity: Severity;
  summary: string;
  triggering_readings: string[];
  pattern_context: string[];
  recommended_action: string;
  acknowledged: boolean;
}

/* ── Helpers ──────────────────────────────────────────────────────────────── */

function severityToScore(s: Severity): number {
  return s === "escalate" || s === "escalate_urgent" ? 0.85 : s === "monitor" ? 0.6 : 0.25;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return fmtDate(iso);
}

function bpSeries(timeline: SymptomLog[]) {
  return timeline
    .filter((e) => e.bp_systolic != null && e.bp_diastolic != null)
    .map((e) => ({
      day: new Date(e.timestamp).toLocaleDateString(undefined, { weekday: "short" }).slice(0, 3),
      sys: e.bp_systolic!,
      dia: e.bp_diastolic!,
    }));
}

function getInitials(name: string): string {
  return name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
}

const BASE_WS = (import.meta.env.VITE_API_URL as string | undefined)
  ?.replace(/^http/, "ws") ?? "ws://localhost:8000";

/* ── Root ─────────────────────────────────────────────────────────────────── */

type View = "panel" | "escalations";

function ClinicianDashboard() {
  const [view, setView] = useState<View>("panel");
  const [rows, setRows] = useState<PanelRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PatientDetail | null>(null);
  const [escalations, setEscalations] = useState<EscalationSummary[]>([]);
  const [panelLoading, setPanelLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    api.get<{ patients: PanelRow[] }>("/clinician/panel")
      .then((r) => {
        setRows(r.patients);
        if (r.patients.length > 0) setSelectedId(r.patients[0].patient_id);
      })
      .catch(console.error)
      .finally(() => setPanelLoading(false));
  }, []);

  useEffect(() => {
    api.get<{ escalations: EscalationSummary[] }>("/clinician/escalations")
      .then((r) => setEscalations(r.escalations))
      .catch(console.error);

    const ws = new WebSocket(`${BASE_WS}/ws/escalations?clinician_id=${CLINICIAN_ID}`);
    ws.onmessage = (e) => {
      try {
        const esc: EscalationSummary = JSON.parse(e.data);
        setEscalations((prev) => [esc, ...prev]);
      } catch {
        /* ignore malformed frames */
      }
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setDetailLoading(true);
    setDetail(null);
    api.get<PatientDetail>(`/clinician/patient/${selectedId}`)
      .then(setDetail)
      .catch(console.error)
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  const newEscalations = escalations.filter((e) => !e.acknowledged).length;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <TopBar view={view} onView={setView} newEscalations={newEscalations} />

      {view === "panel" ? (
        <div className="flex-1 grid lg:grid-cols-[300px_1fr] min-h-0">
          {/* Sidebar */}
          <aside className="border-r border-border bg-surface flex flex-col overflow-hidden">
            <PanelHeader rows={rows} />
            <div className="flex-1 overflow-y-auto">
              {panelLoading ? (
                <div className="p-4 space-y-2">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="h-[72px] rounded-md bg-muted animate-pulse" />
                  ))}
                </div>
              ) : rows.length === 0 ? (
                <p className="px-4 py-8 text-sm text-muted-foreground">No patients assigned.</p>
              ) : (
                <ul className="divide-y divide-border">
                  {rows.map((row) => (
                    <PatientRow
                      key={row.patient_id}
                      row={row}
                      active={row.patient_id === selectedId}
                      onSelect={() => setSelectedId(row.patient_id)}
                    />
                  ))}
                </ul>
              )}
            </div>
          </aside>

          {/* Detail pane */}
          <main className="bg-background overflow-y-auto">
            {detailLoading ? (
              <div className="p-6 space-y-4">
                <div className="h-[88px] rounded-lg bg-muted animate-pulse" />
                <div className="grid grid-cols-2 gap-4">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-40 rounded-lg bg-muted animate-pulse" />
                  ))}
                </div>
              </div>
            ) : detail ? (
              <PatientDetail detail={detail} />
            ) : (
              <div className="flex items-center justify-center h-full min-h-64 text-sm text-muted-foreground">
                Select a patient to view details.
              </div>
            )}
          </main>
        </div>
      ) : (
        <EscalationsInbox
          items={escalations}
          onAck={(id) =>
            setEscalations((es) =>
              es.map((e) => (e.escalation_id === id ? { ...e, acknowledged: true } : e)),
            )
          }
          onOpenPatient={(pid) => {
            setSelectedId(pid);
            setView("panel");
          }}
        />
      )}
    </div>
  );
}

/* ── Top bar ──────────────────────────────────────────────────────────────── */

function TopBar({
  view,
  onView,
  newEscalations,
}: {
  view: View;
  onView: (v: View) => void;
  newEscalations: number;
}) {
  return (
    <header className="h-14 px-5 flex items-center gap-5 bg-surface border-b border-border shrink-0">
      {/* Brand */}
      <div className="flex items-center gap-2 shrink-0">
        <CadenceMark />
        <span className="text-sm font-semibold tracking-tight">Cadence</span>
        <span className="text-border-strong mx-0.5 select-none">·</span>
        <span className="text-xs text-muted-foreground font-medium">Clinician</span>
      </div>

      {/* Nav */}
      <nav className="flex items-center gap-0.5">
        <NavBtn active={view === "panel"} onClick={() => onView("panel")}>
          Patients
        </NavBtn>
        <NavBtn active={view === "escalations"} onClick={() => onView("escalations")}>
          <span className="flex items-center gap-1.5">
            Escalations
            {newEscalations > 0 && (
              <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-risk-escalate text-white text-[10px] font-semibold leading-none tabular-nums">
                {newEscalations}
              </span>
            )}
          </span>
        </NavBtn>
      </nav>

      {/* User */}
      <div className="ml-auto flex items-center gap-3">
        <div className="text-right leading-snug">
          <div className="text-sm font-medium">Dr. Aiyana Reyes, MD</div>
          <div className="text-[11px] text-muted-foreground">Westside Women's Health</div>
        </div>
        <Avatar name="Aiyana Reyes" size="sm" />
      </div>
    </header>
  );
}

function NavBtn({
  children,
  active,
  onClick,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`h-8 px-3 rounded-md text-sm font-medium transition-colors ${
        active
          ? "bg-secondary text-secondary-foreground"
          : "text-muted-foreground hover:text-foreground hover:bg-muted"
      }`}
    >
      {children}
    </button>
  );
}

function CadenceMark() {
  return (
    <svg width="24" height="24" viewBox="0 0 28 28" fill="none" aria-hidden>
      <circle cx="14" cy="14" r="13" stroke="currentColor" strokeOpacity="0.15" />
      <path
        d="M4 16 L9 16 L11 11 L14 20 L17 8 L20 16 L24 16"
        stroke="oklch(0.52 0.20 305)"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" }) {
  const ini = getInitials(name);
  const dim = size === "sm" ? "w-8 h-8 text-xs" : "w-9 h-9 text-[11px]";
  return (
    <div
      className={`${dim} rounded-full bg-primary/10 text-primary border border-primary/20 flex items-center justify-center font-semibold shrink-0 select-none`}
    >
      {ini}
    </div>
  );
}

/* ── Panel sidebar ────────────────────────────────────────────────────────── */

function PanelHeader({ rows }: { rows: PanelRow[] }) {
  const esc = rows.filter((r) => r.severity === "escalate" || r.severity === "escalate_urgent").length;
  const mon = rows.filter((r) => r.severity === "monitor").length;
  const ok = rows.length - esc - mon;

  return (
    <div className="px-4 pt-4 pb-3.5 border-b border-border shrink-0">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold">Patients</h2>
        <span className="h-5 px-2 inline-flex items-center rounded-md bg-muted text-muted-foreground text-[11px] font-medium tabular-nums">
          {rows.length}
        </span>
      </div>
      <div className="flex items-center gap-2.5 text-[11px] flex-wrap">
        <StatusChip dot="bg-risk-escalate" label={`${esc} escalate`} color="text-risk-escalate" />
        <span className="text-border-strong">·</span>
        <StatusChip dot="bg-risk-monitor" label={`${mon} monitor`} color="text-risk-monitor" />
        <span className="text-border-strong">·</span>
        <StatusChip dot="bg-risk-ok" label={`${ok} on track`} color="text-muted-foreground" />
      </div>
    </div>
  );
}

function StatusChip({
  dot,
  label,
  color,
}: {
  dot: string;
  label: string;
  color: string;
}) {
  return (
    <span className={`inline-flex items-center gap-1.5 font-medium ${color}`}>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
      {label}
    </span>
  );
}

function PatientRow({
  row,
  active,
  onSelect,
}: {
  row: PanelRow;
  active: boolean;
  onSelect: () => void;
}) {
  const sev: DisplayRisk = row.severity === "escalate_urgent" ? "escalate" : (row.severity as DisplayRisk);
  const dotColor =
    sev === "escalate" ? "bg-risk-escalate" : sev === "monitor" ? "bg-risk-monitor" : "bg-risk-ok";

  return (
    <li>
      <button
        onClick={onSelect}
        className={`w-full text-left px-4 py-3.5 flex items-start gap-3 transition-colors border-l-2 ${
          active
            ? "border-l-primary bg-accent/20"
            : "border-l-transparent hover:bg-muted/50"
        }`}
      >
        <span className={`mt-[5px] w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <span className="text-sm font-medium truncate">{row.patient_name}</span>
            <RiskBadge risk={sev} small />
          </div>
          <div className="text-xs text-muted-foreground truncate leading-relaxed">
            {row.headline}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1.5 tabular-nums">
            {fmtTime(row.last_check_in)}
          </div>
        </div>
      </button>
    </li>
  );
}

type DisplayRisk = "ok" | "monitor" | "escalate";

function RiskBadge({ risk, small = false }: { risk: DisplayRisk; small?: boolean }) {
  const map: Record<DisplayRisk, { label: string; bg: string; fg: string }> = {
    ok: { label: "On track", bg: "bg-risk-ok-bg", fg: "text-risk-ok" },
    monitor: { label: "Monitor", bg: "bg-risk-monitor-bg", fg: "text-risk-monitor" },
    escalate: { label: "Escalate", bg: "bg-risk-escalate-bg", fg: "text-risk-escalate" },
  };
  const c = map[risk];
  return (
    <span
      className={`inline-flex items-center gap-1 ${c.bg} ${c.fg} font-semibold rounded-md shrink-0 ${
        small ? "text-[10px] px-1.5 py-0.5" : "text-[11px] px-2 py-0.5"
      }`}
    >
      {risk === "escalate" && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse shrink-0" />
      )}
      {c.label}
    </span>
  );
}

/* ── Patient detail ───────────────────────────────────────────────────────── */

function PatientDetail({ detail }: { detail: PatientDetail }) {
  async function runAction(action: "message" | "book" | "flag" | "note", content: string) {
    try {
      const res = await api.post<{ ok: boolean; message: string }>("/clinician/action", {
        patient_id: detail.patient_id,
        action,
        content,
      });
      toast.success(res.message);
    } catch (err) {
      toast.error(`Couldn't ${action}: ${(err as Error).message}`);
    }
  }

  function onMessage() {
    const text = window.prompt(`Message to ${detail.patient_name}`);
    if (text) runAction("message", text);
  }
  function onBook() {
    const when = window.prompt("Book follow-up for when?", "as soon as possible");
    if (when !== null) runAction("book", when);
  }
  function onNote() {
    const note = window.prompt(`Add a note for ${detail.patient_name}`);
    if (note) runAction("note", note);
  }

  const sev: DisplayRisk =
    detail.current_risk?.severity === "escalate_urgent"
      ? "escalate"
      : (detail.current_risk?.severity as DisplayRisk | undefined) ?? "ok";

  const score = detail.current_risk ? severityToScore(detail.current_risk.severity) : 0.25;
  const bp = bpSeries(detail.timeline);
  const starters = detail.visit_summary?.conversation_starters ?? [];
  const briefing = detail.visit_summary?.clinician_facing ?? "";
  const metrics = detail.visit_summary?.key_metrics ?? {};
  const hasMetrics = metrics.check_ins || metrics.avg_bp || metrics.peak_bp || metrics.headache_days;

  return (
    <div>
      {/* ── Page header ── */}
      <div className="sticky top-0 z-10 bg-surface border-b border-border">
        <div className="px-6 py-4 flex items-center justify-between gap-6">
          <div className="flex items-center gap-3 min-w-0">
            <Avatar name={detail.patient_name} />
            <div className="min-w-0">
              <div className="flex items-center gap-2.5 flex-wrap">
                <h1 className="text-base font-semibold truncate">{detail.patient_name}</h1>
                <RiskBadge risk={sev} />
              </div>
              {detail.current_risk && (
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Risk assessed {fmtTime(detail.current_risk.timestamp)}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Btn onClick={onMessage}>Message</Btn>
            <Btn onClick={onBook}>Book sooner</Btn>
            <Btn onClick={() => runAction("flag", "Flagged for nurse review")}>Flag for nurse</Btn>
            <Btn variant="primary" onClick={onNote}>Add note</Btn>
          </div>
        </div>

        {/* Key metrics strip */}
        {hasMetrics && (
          <div className="px-6 pb-4 flex items-center gap-7 border-t border-border pt-3.5">
            {metrics.check_ins && <KeyMetric label="Check-ins" value={metrics.check_ins} />}
            {metrics.avg_bp && <KeyMetric label="Avg BP" value={metrics.avg_bp} />}
            {metrics.peak_bp && <KeyMetric label="Peak BP" value={metrics.peak_bp} />}
            {metrics.headache_days && (
              <KeyMetric label="Headache days" value={metrics.headache_days} />
            )}
          </div>
        )}
      </div>

      {/* ── Content ── */}
      {detail.timeline.length === 0 && !detail.visit_summary ? (
        <div className="m-6 rounded-lg border border-dashed border-border-strong bg-surface px-6 py-10 text-center text-sm text-muted-foreground">
          No check-in data yet for {detail.patient_name}.
        </div>
      ) : (
        <div className="px-6 py-5 space-y-4">
          {/* Row 1: Briefing + Risk */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_296px] gap-4">
            <Card className="p-5">
              <SectionLabel>Pre-visit briefing</SectionLabel>
              <p className="text-sm leading-relaxed">
                {briefing || "No briefing available yet."}
              </p>
            </Card>

            <Card className="p-5">
              <SectionLabel>Risk assessment</SectionLabel>
              <RiskBadge risk={sev} />
              <RiskMeter score={score} />
              <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                {detail.current_risk?.rationale ?? "No risk rationale available."}
              </p>
              {detail.current_risk?.recommended_action && (
                <div className="mt-3 pt-3 border-t border-border">
                  <SectionLabel>Recommended action</SectionLabel>
                  <p className="text-xs leading-relaxed">{detail.current_risk.recommended_action}</p>
                </div>
              )}
            </Card>
          </div>

          {/* Row 2: Patterns + BP */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-5">
              <SectionLabel>Pattern detection</SectionLabel>
              {detail.patterns.length === 0 ? (
                <p className="text-sm text-muted-foreground">No patterns detected.</p>
              ) : (
                <ul className="space-y-2">
                  {detail.patterns.map((p) => {
                    const psev: DisplayRisk =
                      p.severity === "escalate_urgent" ? "escalate" : (p.severity as DisplayRisk);
                    const dotColor =
                      psev === "escalate"
                        ? "bg-risk-escalate"
                        : psev === "monitor"
                          ? "bg-risk-monitor"
                          : "bg-risk-ok";
                    return (
                      <li
                        key={p.title}
                        className="flex items-start gap-3 p-3 rounded-md border border-border bg-muted/30"
                      >
                        <span className={`mt-[5px] w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
                        <div>
                          <div className="text-sm font-medium">{p.title}</div>
                          <div className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                            {p.detail}
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>

            <Card className="p-5">
              <SectionLabel>Blood pressure · {bp.length} readings</SectionLabel>
              {bp.length > 0 ? (
                <>
                  <BPChart data={bp} />
                  <div className="mt-2 flex items-center gap-4 text-[11px] text-muted-foreground">
                    <ChartLegend color="bg-primary" label="Systolic" />
                    <ChartLegend color="bg-accent-foreground" label="Diastolic" />
                    <ChartLegend label="140/90 threshold" dashed />
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No BP readings logged.</p>
              )}
            </Card>
          </div>

          {/* Row 3: Conversation starters + Timeline */}
          <div className="grid grid-cols-1 lg:grid-cols-[296px_1fr] gap-4">
            <Card className="p-5">
              <SectionLabel>Conversation starters</SectionLabel>
              {starters.length === 0 ? (
                <p className="text-sm text-muted-foreground">None generated yet.</p>
              ) : (
                <ol className="space-y-3">
                  {starters.map((s, i) => (
                    <li key={i} className="flex gap-3 text-sm">
                      <span className="shrink-0 text-[11px] font-semibold text-muted-foreground tabular-nums mt-0.5 w-4">
                        {i + 1}.
                      </span>
                      <span className="leading-relaxed">{s}</span>
                    </li>
                  ))}
                </ol>
              )}
              <p className="mt-4 pt-3 border-t border-border text-[11px] text-muted-foreground leading-relaxed">
                Grounded in care plan · independently evaluated
              </p>
            </Card>

            <Card className="p-5">
              <SectionLabel>Timeline · since last visit</SectionLabel>
              {detail.timeline.length === 0 ? (
                <p className="text-sm text-muted-foreground">No check-ins yet.</p>
              ) : (
                <div className="divide-y divide-border">
                  {[...detail.timeline].reverse().map((e, i) => {
                    const flagged = (e.bp_systolic ?? 0) >= 140;
                    const summary =
                      e.raw_text ?? `BP ${e.bp_systolic ?? "—"}/${e.bp_diastolic ?? "—"}`;
                    return (
                      <div key={i} className="py-3 first:pt-0 last:pb-0 flex items-start gap-3">
                        <span
                          className={`mt-[5px] w-2 h-2 rounded-full shrink-0 ${
                            flagged ? "bg-risk-escalate" : "bg-border-strong"
                          }`}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm">{summary}</div>
                          {e.notes && (
                            <div className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                              {e.notes}
                            </div>
                          )}
                        </div>
                        <div className="text-[11px] text-muted-foreground shrink-0 tabular-nums">
                          {fmtDate(e.timestamp)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          </div>

          <p className="pb-2 text-[11px] text-muted-foreground text-center">
            All entries traced in Arize · LLM-as-judge confidence on most recent escalation: 0.97
          </p>
        </div>
      )}
    </div>
  );
}

/* ── Escalations inbox ────────────────────────────────────────────────────── */

function EscalationsInbox({
  items,
  onAck,
  onOpenPatient,
}: {
  items: EscalationSummary[];
  onAck: (id: string) => void;
  onOpenPatient: (pid: string) => void;
}) {
  const unread = items.filter((e) => !e.acknowledged).length;
  const acked = items.filter((e) => e.acknowledged).length;

  return (
    <div className="flex-1 flex flex-col">
      {/* Page header — same height/style as patient detail header */}
      <div className="bg-surface border-b border-border px-6 py-4 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-base font-semibold">Escalations</h1>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Structured summaries · independently evaluated before delivery
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          <span>
            <span className="font-semibold text-foreground tabular-nums">{unread}</span> unread
          </span>
          <span className="text-border-strong">·</span>
          <span>
            <span className="font-semibold text-foreground tabular-nums">{acked}</span> acknowledged
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-5">
          {items.length === 0 ? (
            <div className="py-16 text-center text-sm text-muted-foreground">
              No escalations yet.
            </div>
          ) : (
            <ul className="space-y-3">
              {items.map((e) => {
                const sev: DisplayRisk =
                  e.severity === "escalate_urgent" ? "escalate" : (e.severity as DisplayRisk);
                return (
                  <li
                    key={e.escalation_id}
                    className={`rounded-lg border bg-surface ${
                      !e.acknowledged ? "border-risk-escalate/30" : "border-border"
                    }`}
                  >
                    <div className="p-5">
                      {/* Card header */}
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-center gap-3 min-w-0">
                          <Avatar name={e.patient_name} />
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-semibold">{e.patient_name}</span>
                              <RiskBadge risk={!e.acknowledged ? "escalate" : sev} small />
                            </div>
                            <div className="text-[11px] text-muted-foreground mt-0.5 tabular-nums">
                              {fmtTime(e.timestamp)}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {!e.acknowledged && (
                            <Btn onClick={() => onAck(e.escalation_id)}>Acknowledge</Btn>
                          )}
                          <Btn variant="primary" onClick={() => onOpenPatient(e.patient_id)}>
                            Open patient
                          </Btn>
                        </div>
                      </div>

                      <p className="mt-4 text-sm leading-relaxed">{e.summary}</p>

                      {e.triggering_readings.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {e.triggering_readings.map((v) => (
                            <span
                              key={v}
                              className="px-2 py-1 text-xs rounded-md bg-secondary text-secondary-foreground font-mono"
                            >
                              {v}
                            </span>
                          ))}
                        </div>
                      )}

                      <div className="mt-4 pt-3 border-t border-border">
                        <SectionLabel>Recommended action</SectionLabel>
                        <p className="text-sm">{e.recommended_action}</p>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Shared primitives ────────────────────────────────────────────────────── */

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-border bg-surface ${className}`}>{children}</div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-2.5">
      {children}
    </div>
  );
}

function Btn({
  children,
  variant = "secondary",
  onClick,
}: {
  children: React.ReactNode;
  variant?: "primary" | "secondary";
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center h-8 px-3 rounded-md text-sm font-medium transition-colors ${
        variant === "primary"
          ? "bg-primary text-primary-foreground hover:bg-primary/90"
          : "bg-surface border border-border text-foreground hover:bg-muted"
      }`}
    >
      {children}
    </button>
  );
}

function KeyMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider leading-none mb-1">
        {label}
      </div>
      <div className="text-sm font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function RiskMeter({ score }: { score: number }) {
  return (
    <div className="mt-3 mb-1 h-1.5 rounded-full bg-muted overflow-hidden">
      <div
        className="h-full rounded-full bg-gradient-to-r from-risk-ok via-risk-monitor to-risk-escalate transition-all"
        style={{ width: `${score * 100}%` }}
      />
    </div>
  );
}

function ChartLegend({
  color,
  label,
  dashed,
}: {
  color?: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {dashed ? (
        <span className="w-3 h-px border-t border-dashed border-risk-escalate" />
      ) : (
        <span className={`w-2 h-2 rounded-sm ${color}`} />
      )}
      {label}
    </span>
  );
}

function BPChart({ data }: { data: { day: string; sys: number; dia: number }[] }) {
  if (!data.length) return null;
  const W = 520;
  const H = 160;
  const PAD = { l: 28, r: 8, t: 8, b: 20 };
  const xs = (i: number) =>
    PAD.l + (i * (W - PAD.l - PAD.r)) / Math.max(1, data.length - 1);
  const yMin = 70;
  const yMax = 150;
  const ys = (v: number) =>
    PAD.t + (H - PAD.t - PAD.b) * (1 - (v - yMin) / (yMax - yMin));

  const sysPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${xs(i)},${ys(d.sys)}`).join(" ");
  const diaPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${xs(i)},${ys(d.dia)}`).join(" ");
  const threshold = ys(140);

  return (
    <div className="mt-2 w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="none">
        {[80, 100, 120, 140].map((v) => (
          <g key={v}>
            <line
              x1={PAD.l} x2={W - PAD.r}
              y1={ys(v)} y2={ys(v)}
              stroke="oklch(0.91 0.012 300)"
              strokeWidth="1"
            />
            <text x={4} y={ys(v) + 3} fontSize="9" fill="oklch(0.50 0.04 295)">{v}</text>
          </g>
        ))}
        <line
          x1={PAD.l} x2={W - PAD.r}
          y1={threshold} y2={threshold}
          stroke="oklch(0.5 0.2 25)"
          strokeWidth="1"
          strokeDasharray="4 4"
          opacity="0.6"
        />
        <path d={sysPath} stroke="oklch(0.52 0.20 305)" strokeWidth="2" fill="none" />
        <path d={diaPath} stroke="oklch(0.38 0.15 305)" strokeWidth="2" fill="none" opacity="0.6" />
        {data.map((d, i) => (
          <g key={i}>
            <circle
              cx={xs(i)} cy={ys(d.sys)}
              r={d.sys >= 140 ? 4 : 2.5}
              fill={d.sys >= 140 ? "oklch(0.5 0.2 25)" : "oklch(0.52 0.20 305)"}
            />
            <circle cx={xs(i)} cy={ys(d.dia)} r="2.5" fill="oklch(0.38 0.15 305)" opacity="0.7" />
            <text
              x={xs(i)} y={H - 4}
              fontSize="9"
              fill="oklch(0.50 0.04 295)"
              textAnchor="middle"
            >
              {d.day}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
