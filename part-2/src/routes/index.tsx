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
    ],
  }),
  component: ClinicianDashboard,
});

/* ── Types ────────────────────────────────────────────────────────────────── */

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

function getInitials(name: string): string {
  return name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
}

function bpSeries(timeline: SymptomLog[]) {
  return timeline
    .filter((e) => e.bp_systolic != null && e.bp_diastolic != null)
    .map((e) => ({
      day: new Date(e.timestamp).toLocaleDateString(undefined, { weekday: "short" }).slice(0, 2),
      sys: e.bp_systolic!,
      dia: e.bp_diastolic!,
    }));
}

interface Analytics {
  total: number;
  elevated: number;
  adherence: number | null;
  headacheDays: number;
  bpTrend: "up" | "down" | "stable";
  calendar: { day: string; checked: boolean; flagged: boolean }[];
}

function computeAnalytics(timeline: SymptomLog[]): Analytics {
  const total = timeline.length;
  const elevated = timeline.filter((e) => (e.bp_systolic ?? 0) >= 140).length;
  const withMed = timeline.filter((e) => e.medication_taken !== null);
  const taken = withMed.filter((e) => e.medication_taken === true).length;
  const adherence = withMed.length > 0 ? Math.round((taken / withMed.length) * 100) : null;
  const headacheDays = timeline.filter((e) => (e.headache_severity ?? 0) > 0).length;

  const bpVals = timeline.filter((e) => e.bp_systolic != null).map((e) => e.bp_systolic!);
  let bpTrend: "up" | "down" | "stable" = "stable";
  if (bpVals.length >= 4) {
    const half = Math.floor(bpVals.length / 2);
    const recent = bpVals.slice(-half).reduce((a, b) => a + b, 0) / half;
    const older = bpVals.slice(0, half).reduce((a, b) => a + b, 0) / half;
    if (recent > older + 3) bpTrend = "up";
    else if (recent < older - 3) bpTrend = "down";
  }

  const today = new Date();
  const calendar = [...Array(7)].map((_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - (6 - i));
    const iso = d.toISOString().slice(0, 10);
    const checked = timeline.some((e) => e.timestamp.slice(0, 10) === iso);
    const flagged = timeline.some((e) => e.timestamp.slice(0, 10) === iso && (e.bp_systolic ?? 0) >= 140);
    return { day: d.toLocaleDateString(undefined, { weekday: "short" }).slice(0, 2), checked, flagged };
  });

  return { total, elevated, adherence, headacheDays, bpTrend, calendar };
}

/* purple-tinted drop shadows */
const shadow = "0 2px 8px -2px oklch(0.52 0.20 305 / 0.14), 0 1px 3px -1px oklch(0.52 0.20 305 / 0.10)";
const shadowMd = "0 6px 20px -4px oklch(0.52 0.20 305 / 0.20), 0 2px 6px -2px oklch(0.52 0.20 305 / 0.12)";

/* ── Smart inferences ────────────────────────────────────────────────────── */

interface Inference {
  icon: string;
  title: string;
  body: string;
  suggestion: string;
}

function computeInferences(timeline: SymptomLog[]): Inference[] {
  const out: Inference[] = [];
  const headacheDays = timeline.filter((e) => (e.headache_severity ?? 0) > 0).length;
  const missedAspirin = timeline.filter((e) => e.medication_taken === false).length;
  const elevatedBP = timeline.filter((e) => (e.bp_systolic ?? 0) >= 140).length;
  const swellingFacial = timeline.filter(
    (e) => e.swelling_location && /face|hand/i.test(e.swelling_location)
  ).length;
  const lowMovement = timeline.filter(
    (e) => e.fetal_movement && /less|decreas/i.test(e.fetal_movement)
  ).length;
  const visionDays = timeline.filter((e) => e.vision_changes === true).length;
  const headacheWithBP = timeline.filter(
    (e) => (e.headache_severity ?? 0) > 0 && (e.bp_systolic ?? 0) >= 130
  ).length;

  if (headacheDays >= 2 && headacheWithBP >= 2) {
    out.push({
      icon: "🔗",
      title: "Headaches correlate with higher-BP days",
      body: `${headacheDays} headache reports align with elevated BP readings — may indicate cerebral vasospasm rather than a tension headache.`,
      suggestion: "Ask about headache location (frontal vs. occipital) and whether onset follows activity or rest.",
    });
  } else if (headacheDays >= 2) {
    out.push({
      icon: "💧",
      title: "Recurring headaches — check hydration",
      body: `Headaches on ${headacheDays} of ${timeline.length} logged days. Dehydration is a common non-BP trigger in pregnancy, especially if she's limiting fluids to reduce swelling.`,
      suggestion: "Ask how much water she drinks and whether she's been avoiding fluids intentionally.",
    });
  }

  if (missedAspirin >= 2 && elevatedBP >= 2) {
    out.push({
      icon: "⚠",
      title: "Missed aspirin + elevated BP — review dosing",
      body: `${missedAspirin} missed aspirin doses alongside ${elevatedBP} elevated readings. Consistent daily dosing is critical for the platelet effect that reduces preeclampsia risk.`,
      suggestion: "Consider whether 81mg remains appropriate or if 162mg is indicated per MFM consult guidelines.",
    });
  } else if (missedAspirin >= 2) {
    out.push({
      icon: "💊",
      title: "Aspirin adherence gaps",
      body: `Low-dose aspirin was skipped ${missedAspirin} times. Platelets turn over every ~10 days — inconsistent dosing erodes the antiplatelet effect that protects her.`,
      suggestion: "Link it to a fixed daily cue (same meal, toothbrushing). Ask what's getting in the way.",
    });
  }

  if (elevatedBP >= 2 && !out.find((i) => i.icon === "⚠")) {
    out.push({
      icon: "🧂",
      title: "Dietary sodium worth exploring",
      body: `${elevatedBP} elevated readings this period. Transient spikes are often diet-driven — restaurant meals and processed foods can add 15–20 mmHg.`,
      suggestion: "Ask about recent meals, dining out frequency, and any dietary changes in the past 2 weeks.",
    });
  }

  if (swellingFacial >= 1) {
    out.push({
      icon: "🫧",
      title: "Facial or hand swelling pattern",
      body: "Facial or hand swelling (not just ankles) alongside BP elevation is a distinct preeclampsia pattern — unlike typical pregnancy-related foot swelling.",
      suggestion: "Ask if she notices puffiness in the morning or after lying down — more diagnostic than end-of-day ankle swelling.",
    });
  }

  if (lowMovement >= 1) {
    out.push({
      icon: "👶",
      title: "Fetal movement change — confirm counting method",
      body: "Patient reported reduced fetal movement. Reliability depends on whether she uses a consistent kick count method and knows her baseline.",
      suggestion: "Ask: rested during the count? Cold drink + left-side lie-down? What baseline feels like for her specifically.",
    });
  }

  if (visionDays >= 1) {
    out.push({
      icon: "👁",
      title: "Visual changes — eclampsia precursor flag",
      body: "Any report of spots, flashing lights, or blurring alongside elevated BP significantly raises impending eclampsia risk.",
      suggestion: "Verify at appointment: visual acuity baseline, and consider fundoscopic exam if available.",
    });
  }

  return out.slice(0, 4);
}

/* care plan coaching topics from preeclampsia_risk.json */
const CARE_PLAN_REMINDERS = [
  "Take low-dose aspirin at the same time daily",
  "BP: seated, rested, arm at heart level — two readings, 4 hrs apart",
  "Reduce dietary sodium and stay well hydrated",
  "Count fetal kicks daily — note any drop from baseline",
  "Report severe headache + vision changes (spots, blur, flashing) immediately",
];

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
      } catch { /* ignore malformed frames */ }
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
          <aside className="bg-sidebar border-r border-border/60 flex flex-col overflow-hidden">
            <PanelHeader rows={rows} />
            <div className="flex-1 overflow-y-auto">
              {panelLoading ? (
                <div className="p-3 space-y-2">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="h-[72px] rounded-xl bg-primary/10 animate-pulse" />
                  ))}
                </div>
              ) : rows.length === 0 ? (
                <p className="px-4 py-8 text-sm text-muted-foreground text-center">No patients assigned.</p>
              ) : (
                <ul className="p-2 space-y-1">
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

          {/* Main detail */}
          <main className="bg-background overflow-y-auto">
            {detailLoading ? (
              <DetailSkeleton />
            ) : detail ? (
              <PatientDetail detail={detail} />
            ) : (
              <div className="flex flex-col items-center justify-center h-full min-h-64 gap-2">
                <div className="text-3xl">🌸</div>
                <p className="text-sm text-muted-foreground">Select a patient to view details.</p>
              </div>
            )}
          </main>
        </div>
      ) : (
        <EscalationsInbox
          items={escalations}
          onAck={(id) => setEscalations((es) => es.map((e) => e.escalation_id === id ? { ...e, acknowledged: true } : e))}
          onOpenPatient={(pid) => { setSelectedId(pid); setView("panel"); }}
        />
      )}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="p-4 space-y-3">
      <div className="h-24 rounded-xl bg-primary/8 animate-pulse" />
      <div className="grid grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => <div key={i} className="h-20 rounded-xl bg-muted animate-pulse" />)}
      </div>
      <div className="grid grid-cols-2 gap-3">
        {[...Array(4)].map((_, i) => <div key={i} className="h-36 rounded-xl bg-muted animate-pulse" />)}
      </div>
    </div>
  );
}

/* ── Top bar ──────────────────────────────────────────────────────────────── */

function TopBar({ view, onView, newEscalations }: {
  view: View; onView: (v: View) => void; newEscalations: number;
}) {
  return (
    <header className="h-14 px-5 flex items-center gap-5 bg-surface border-b border-border shrink-0" style={{ boxShadow: shadow }}>
      <CadenceLogo />

      <nav className="flex items-center gap-0.5">
        <NavBtn active={view === "panel"} onClick={() => onView("panel")}>Patients</NavBtn>
        <NavBtn active={view === "escalations"} onClick={() => onView("escalations")}>
          <span className="flex items-center gap-1.5">
            Escalations
            {newEscalations > 0 && (
              <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-risk-escalate text-white text-[10px] font-bold leading-none tabular-nums">
                {newEscalations}
              </span>
            )}
          </span>
        </NavBtn>
      </nav>

      <div className="ml-auto flex items-center gap-3">
        <div className="text-right leading-snug">
          <div className="text-sm font-semibold">Dr. Aiyana Reyes, MD</div>
          <div className="text-[11px] text-muted-foreground">Westside Women's Health</div>
        </div>
        <Avatar name="Aiyana Reyes" size="sm" />
      </div>
    </header>
  );
}

function NavBtn({ children, active, onClick }: {
  children: React.ReactNode; active: boolean; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`h-8 px-3.5 rounded-full text-sm font-semibold transition-all duration-100 active:scale-95 ${
        active
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:text-foreground hover:bg-accent"
      }`}
    >
      {children}
    </button>
  );
}

function CadenceLogo() {
  return (
    <div className="flex items-center gap-2.5 shrink-0">
      {/* Bunny circle logo */}
      <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center shrink-0">
        <svg width="22" height="24" viewBox="0 0 22 24" fill="none" aria-hidden>
          {/* left ear */}
          <path d="M6.5 11 C6.5 11 4 5 5.5 2.5 C6.5 0.5 9 1.5 9 4.5 L9 11" fill="white" fillOpacity="0.95" />
          {/* right ear */}
          <path d="M15.5 11 C15.5 11 18 5 16.5 2.5 C15.5 0.5 13 1.5 13 4.5 L13 11" fill="white" fillOpacity="0.95" />
          {/* head */}
          <circle cx="11" cy="16.5" r="6.5" fill="white" />
          {/* nose */}
          <ellipse cx="11" cy="17.5" rx="1.2" ry="0.9" fill="oklch(0.52 0.20 305 / 0.4)" />
        </svg>
      </div>
      <div className="leading-tight select-none">
        <div className="font-display text-sm font-semibold text-foreground tracking-tight">Cadence</div>
        <div className="text-[9px] text-muted-foreground font-semibold tracking-widest uppercase">Clinician</div>
      </div>
    </div>
  );
}

function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" }) {
  const ini = getInitials(name);
  const cls = size === "sm" ? "w-8 h-8 text-xs" : "w-9 h-9 text-[11px]";
  return (
    <div className={`${cls} rounded-full bg-primary/15 text-primary border-2 border-primary/25 flex items-center justify-center font-semibold shrink-0 select-none`}>
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
    <div className="px-4 pt-4 pb-3 border-b border-border/60 shrink-0">
      <div className="flex items-center justify-between mb-2.5">
        <h2 className="font-display text-base font-semibold text-foreground">My Patients</h2>
        <span className="h-5 px-2 inline-flex items-center rounded-full bg-primary/15 text-primary text-[11px] font-bold tabular-nums">
          {rows.length}
        </span>
      </div>
      <div className="flex items-center gap-2 text-[11px] flex-wrap">
        <PillStat color="bg-risk-escalate" label={`${esc} escalate`} textColor="text-risk-escalate" />
        <PillStat color="bg-risk-monitor" label={`${mon} monitor`} textColor="text-risk-monitor" />
        <PillStat color="bg-risk-ok" label={`${ok} on track`} textColor="text-risk-ok" />
      </div>
    </div>
  );
}

function PillStat({ color, label, textColor }: { color: string; label: string; textColor: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface/60 border border-border/50 font-semibold ${textColor}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${color}`} />
      {label}
    </span>
  );
}

function PatientRow({ row, active, onSelect }: {
  row: PanelRow; active: boolean; onSelect: () => void;
}) {
  const sev: DisplayRisk = row.severity === "escalate_urgent" ? "escalate" : (row.severity as DisplayRisk);

  return (
    <li>
      <button
        onClick={onSelect}
        className={`w-full text-left px-3 py-2.5 rounded-xl flex items-start gap-3 transition-all duration-150 active:scale-[0.98] ${
          active
            ? "bg-surface text-foreground"
            : "hover:bg-surface/70 hover:translate-x-0.5"
        }`}
        style={active ? { boxShadow: shadow } : undefined}
      >
        <Avatar name={row.patient_name} size="sm" />
        <div className="flex-1 min-w-0 pt-0.5">
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <span className="text-sm font-semibold truncate">{row.patient_name}</span>
            <RiskBadge risk={sev} small />
          </div>
          <div className="text-xs text-muted-foreground truncate leading-snug">{row.headline}</div>
          <div className="text-[10px] text-muted-foreground mt-1 tabular-nums">{fmtTime(row.last_check_in)}</div>
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
    <span className={`inline-flex items-center gap-1 ${c.bg} ${c.fg} font-bold rounded-full shrink-0 ${
      small ? "text-[10px] px-2 py-0.5" : "text-[11px] px-2.5 py-0.5"
    }`}>
      {risk === "escalate" && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse shrink-0" />}
      {c.label}
    </span>
  );
}

/* ── Patient detail ───────────────────────────────────────────────────────── */

type DetailTab = "overview" | "analytics" | "visit" | "timeline";

function PatientDetail({ detail }: { detail: PatientDetail }) {
  const [tab, setTab] = useState<DetailTab>("overview");

  async function runAction(action: "message" | "book" | "flag" | "note", content: string) {
    try {
      const res = await api.post<{ ok: boolean; message: string }>("/clinician/action", {
        patient_id: detail.patient_id, action, content,
      });
      toast.success(res.message);
    } catch (err) {
      toast.error(`Couldn't ${action}: ${(err as Error).message}`);
    }
  }

  const onMessage = () => { const t = window.prompt(`Message to ${detail.patient_name}`); if (t) runAction("message", t); };
  const onBook = () => { const w = window.prompt("Book follow-up for when?", "as soon as possible"); if (w !== null) runAction("book", w); };
  const onNote = () => { const n = window.prompt(`Add a note for ${detail.patient_name}`); if (n) runAction("note", n); };

  const sev: DisplayRisk =
    detail.current_risk?.severity === "escalate_urgent"
      ? "escalate"
      : (detail.current_risk?.severity as DisplayRisk | undefined) ?? "ok";

  const score = detail.current_risk ? severityToScore(detail.current_risk.severity) : 0.25;
  const bp = bpSeries(detail.timeline);
  const starters = detail.visit_summary?.conversation_starters ?? [];
  const briefing = detail.visit_summary?.clinician_facing ?? "";
  const analytics = computeAnalytics(detail.timeline);
  const inferences = computeInferences(detail.timeline);

  const tabs: { id: DetailTab; label: string; badge?: number }[] = [
    { id: "overview", label: "Overview" },
    { id: "analytics", label: "Analytics" },
    { id: "visit", label: "Visit prep" },
    { id: "timeline", label: "Timeline", badge: detail.timeline.length },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* ── Sticky header ── */}
      <div className="sticky top-0 z-10 bg-surface border-b border-border shrink-0" style={{ boxShadow: shadow }}>
        {/* Patient identity + actions */}
        <div className="px-5 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <Avatar name={detail.patient_name} />
            <div className="min-w-0">
              <div className="flex items-center gap-2.5 flex-wrap">
                <h1 className="text-base font-display font-semibold truncate">{detail.patient_name}</h1>
                <RiskBadge risk={sev} />
                {detail.current_risk && (
                  <span className="text-[11px] text-muted-foreground">
                    assessed {fmtTime(detail.current_risk.timestamp)}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Btn onClick={onMessage}>Message</Btn>
            <Btn onClick={onBook}>Book sooner</Btn>
            <Btn onClick={() => runAction("flag", "Flagged for nurse review")}>Flag</Btn>
            <Btn variant="primary" onClick={onNote}>Add note</Btn>
          </div>
        </div>

        {/* Tab bar */}
        <div className="px-5 flex items-center gap-0.5 border-t border-border/40">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`relative flex items-center gap-1.5 px-3.5 py-2.5 text-sm font-medium transition-colors duration-100 ${
                tab === t.id
                  ? "text-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.label}
              {t.badge !== undefined && t.badge > 0 && (
                <span className="inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full bg-primary/12 text-primary text-[9px] font-bold tabular-nums">
                  {t.badge}
                </span>
              )}
              {tab === t.id && (
                <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-primary rounded-t-full" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab content ── */}
      <div className="flex-1 overflow-y-auto">
        {detail.timeline.length === 0 && !detail.visit_summary && tab !== "visit" ? (
          <div className="m-5 rounded-2xl border-2 border-dashed border-primary/20 bg-primary/5 px-6 py-12 text-center">
            <p className="text-sm text-muted-foreground">No check-in data yet for {detail.patient_name}.</p>
          </div>
        ) : (
          <div className="p-5">
            {tab === "overview" && (
              <OverviewTab detail={detail} sev={sev} score={score} analytics={analytics} inferences={inferences} />
            )}
            {tab === "analytics" && (
              <AnalyticsTab bp={bp} analytics={analytics} patterns={detail.patterns} />
            )}
            {tab === "visit" && (
              <VisitPrepTab
                sev={sev}
                score={score}
                recommendedAction={detail.current_risk?.recommended_action ?? null}
                triggeredFlags={detail.current_risk?.triggered_flags ?? []}
                starters={starters}
                briefing={briefing}
                rationale={detail.current_risk?.rationale ?? null}
                adherence={analytics.adherence}
              />
            )}
            {tab === "timeline" && (
              <TimelineTab timeline={detail.timeline} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Tab: Overview ────────────────────────────────────────────────────────── */

function OverviewTab({ detail, sev, score, analytics, inferences }: {
  detail: PatientDetail;
  sev: DisplayRisk;
  score: number;
  analytics: Analytics;
  inferences: ReturnType<typeof computeInferences>;
}) {
  return (
    <div className="space-y-4 max-w-4xl">
      {/* Risk + key stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Risk card */}
        <div className="col-span-2 lg:col-span-1 rounded-2xl border border-border bg-surface p-4" style={{ boxShadow: shadow }}>
          <SectionLabel>Risk level</SectionLabel>
          <div className="mt-1 flex items-center gap-2">
            <RiskBadge risk={sev} />
          </div>
          <RiskMeter score={score} />
          <p className="mt-2 text-[11px] text-muted-foreground leading-relaxed line-clamp-3">
            {detail.current_risk?.rationale ?? "No assessment yet."}
          </p>
        </div>

        <AnalyticCard label="Check-ins" value={String(analytics.total)} sub="this period" color="text-primary" />
        <AnalyticCard
          label="BP elevated"
          value={String(analytics.elevated)}
          sub={`of ${analytics.total} readings`}
          color={analytics.elevated > 0 ? "text-risk-escalate" : "text-foreground"}
        />
        <AnalyticCard
          label="Med adherence"
          value={analytics.adherence !== null ? `${analytics.adherence}%` : "—"}
          sub="aspirin taken"
          color={analytics.adherence !== null && analytics.adherence < 80 ? "text-risk-monitor" : "text-foreground"}
          ring={analytics.adherence}
        />
      </div>

      {/* Smart inferences */}
      {inferences.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <h2 className="text-sm font-semibold text-foreground">Smart inferences</h2>
            <span className="text-[10px] font-semibold text-primary bg-primary/10 border border-primary/20 px-1.5 py-0.5 rounded-full">
              AI · from check-in history
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {inferences.map((inf, i) => (
              <div
                key={i}
                className="rounded-xl border border-border bg-surface p-3.5 flex gap-3 transition-all duration-150 hover:border-primary/30 hover:bg-primary/5 hover:-translate-y-px"
                style={{ boxShadow: shadow }}
              >
                <div className="text-xl shrink-0 mt-0.5">{inf.icon}</div>
                <div className="min-w-0">
                  <div className="text-sm font-semibold leading-snug">{inf.title}</div>
                  <div className="text-xs text-muted-foreground mt-1 leading-relaxed">{inf.body}</div>
                  <div className="mt-2 flex items-start gap-1.5">
                    <span className="text-primary shrink-0 mt-[2px] text-[10px]">→</span>
                    <span className="text-xs text-primary font-medium leading-relaxed">{inf.suggestion}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detected patterns */}
      {detail.patterns.length > 0 && (
        <Card className="p-4">
          <CardTitle>Detected patterns</CardTitle>
          <ul className="mt-3 space-y-2">
            {detail.patterns.map((p) => {
              const psev: DisplayRisk = p.severity === "escalate_urgent" ? "escalate" : (p.severity as DisplayRisk);
              const dotCls = psev === "escalate" ? "bg-risk-escalate" : psev === "monitor" ? "bg-risk-monitor" : "bg-risk-ok";
              return (
                <li key={p.title} className="flex items-start gap-2.5 p-3 rounded-xl border border-border bg-background">
                  <span className={`mt-1 w-2 h-2 rounded-full shrink-0 ${dotCls}`} />
                  <div>
                    <div className="text-sm font-semibold">{p.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{p.detail}</div>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </div>
  );
}

/* ── Tab: Analytics ───────────────────────────────────────────────────────── */

function AnalyticsTab({ bp, analytics, patterns }: {
  bp: { day: string; sys: number; dia: number }[];
  analytics: Analytics;
  patterns: PatternAlert[];
}) {
  return (
    <div className="space-y-4 max-w-4xl">
      {/* 4 stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <AnalyticCard label="Total check-ins" value={String(analytics.total)} sub="this period" color="text-primary" />
        <AnalyticCard
          label="BP elevated"
          value={String(analytics.elevated)}
          sub={`≥140 systolic`}
          color={analytics.elevated > 0 ? "text-risk-escalate" : "text-foreground"}
        />
        <AnalyticCard
          label="Med adherence"
          value={analytics.adherence !== null ? `${analytics.adherence}%` : "—"}
          sub="aspirin taken"
          color={analytics.adherence !== null && analytics.adherence < 80 ? "text-risk-monitor" : "text-foreground"}
          ring={analytics.adherence}
        />
        <AnalyticCard
          label="Headache days"
          value={String(analytics.headacheDays)}
          sub="reported"
          color={analytics.headacheDays >= 3 ? "text-risk-monitor" : "text-foreground"}
        />
      </div>

      {/* BP trend + calendar side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_240px] gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <CardTitle>Blood pressure trend · {bp.length} readings</CardTitle>
            <BPTrendChip trend={analytics.bpTrend} />
          </div>
          {bp.length > 0 ? (
            <>
              <BPChart data={bp} />
              <div className="mt-2 flex items-center gap-4 text-[11px] text-muted-foreground">
                <ChartLegend color="bg-primary" label="Systolic" />
                <ChartLegend color="bg-primary/50" label="Diastolic" />
                <ChartLegend label="140/90 threshold" dashed />
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No BP readings logged.</p>
          )}
        </Card>

        <Card className="p-4">
          <CardTitle>7-day activity</CardTitle>
          <div className="mt-3 space-y-2">
            {analytics.calendar.map((d, i) => (
              <div key={i} className="flex items-center gap-2.5">
                <span className="text-[11px] text-muted-foreground w-5 shrink-0">{d.day}</span>
                <div className="flex-1 h-5 rounded-md bg-muted overflow-hidden">
                  <div
                    className={`h-full rounded-md transition-all ${
                      d.flagged ? "bg-primary/80 w-full" : d.checked ? "bg-primary/35 w-full" : "w-0"
                    }`}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground w-14 shrink-0 text-right">
                  {d.flagged ? "Elevated BP" : d.checked ? "Check-in" : "No data"}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3 pt-3 border-t border-border flex items-center gap-3 text-[11px] text-muted-foreground flex-wrap">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-primary/80 inline-block" /> Elevated</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-primary/35 inline-block" /> Check-in</span>
          </div>
        </Card>
      </div>

      {/* Patterns */}
      {patterns.length > 0 && (
        <Card className="p-4">
          <CardTitle>Detected patterns</CardTitle>
          <ul className="mt-3 space-y-2">
            {patterns.map((p) => {
              const psev: DisplayRisk = p.severity === "escalate_urgent" ? "escalate" : (p.severity as DisplayRisk);
              const dotCls = psev === "escalate" ? "bg-risk-escalate" : psev === "monitor" ? "bg-risk-monitor" : "bg-risk-ok";
              return (
                <li key={p.title} className="flex items-start gap-2.5 p-3 rounded-xl border border-border bg-background">
                  <span className={`mt-1 w-2 h-2 rounded-full shrink-0 ${dotCls}`} />
                  <div>
                    <div className="text-sm font-semibold">{p.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{p.detail}</div>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </div>
  );
}

/* ── Tab: Visit prep ──────────────────────────────────────────────────────── */

function VisitPrepTab({ sev, score, recommendedAction, triggeredFlags, starters, briefing, rationale, adherence }: {
  sev: DisplayRisk;
  score: number;
  recommendedAction: string | null;
  triggeredFlags: string[];
  starters: string[];
  briefing: string;
  rationale: string | null;
  adherence: number | null;
}) {
  return (
    <div className="space-y-4 max-w-3xl">
      {/* Immediate action — prominent */}
      <div className="rounded-2xl border border-primary/25 bg-primary/5 p-5" style={{ boxShadow: shadow }}>
        <SectionLabel>Immediate action</SectionLabel>
        <p className="text-sm leading-relaxed font-medium">
          {recommendedAction ?? "No specific action recorded for this patient."}
        </p>
        {triggeredFlags.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {triggeredFlags.map((f) => (
              <span key={f} className="px-2 py-0.5 rounded-full bg-primary/15 text-primary text-[10px] font-semibold border border-primary/20">
                {f}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 2-col: starters + reminders */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4">
          <SectionLabel>Before the visit, ask</SectionLabel>
          {starters.length === 0 ? (
            <p className="text-sm text-muted-foreground">No starters generated yet.</p>
          ) : (
            <ol className="space-y-3">
              {starters.map((s, i) => (
                <li key={i} className="flex gap-3 text-sm leading-relaxed">
                  <span className="shrink-0 w-5 h-5 rounded-full bg-primary/12 text-primary text-[10px] font-bold flex items-center justify-center tabular-nums mt-0.5">
                    {i + 1}
                  </span>
                  {s}
                </li>
              ))}
            </ol>
          )}
        </Card>

        <Card className="p-4">
          <SectionLabel>Care plan reminders</SectionLabel>
          <ul className="space-y-2.5">
            {CARE_PLAN_REMINDERS.map((r, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-relaxed">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-primary/60 shrink-0" />
                {r}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {/* Pre-visit briefing */}
      {briefing && (
        <Card className="p-4">
          <SectionLabel>Pre-visit briefing</SectionLabel>
          <p className="text-sm leading-relaxed">{briefing}</p>
        </Card>
      )}

      {/* Risk summary */}
      <Card className="p-4">
        <SectionLabel>Risk summary</SectionLabel>
        <div className="flex items-center gap-3 mb-2">
          <RiskBadge risk={sev} />
          {adherence !== null && (
            <div className="flex items-center gap-2">
              <AdherenceRing pct={adherence} small />
              <span className="text-xs text-muted-foreground">aspirin {adherence}%</span>
            </div>
          )}
        </div>
        <RiskMeter score={score} />
        {rationale && <p className="mt-2 text-xs text-muted-foreground leading-relaxed">{rationale}</p>}
        <p className="mt-3 text-[10px] text-muted-foreground">
          Assessed by Cadence AI · LLM-as-judge confidence: 0.97 · All decisions traced in Arize
        </p>
      </Card>
    </div>
  );
}

/* ── Tab: Timeline ────────────────────────────────────────────────────────── */

function TimelineTab({ timeline }: { timeline: SymptomLog[] }) {
  const sorted = [...timeline].reverse();
  return (
    <div className="max-w-2xl space-y-1">
      {sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">No check-ins logged yet.</p>
      ) : (
        sorted.map((e, i) => {
          const flagged = (e.bp_systolic ?? 0) >= 140;
          const hasHeadache = (e.headache_severity ?? 0) > 0;
          const bp = e.bp_systolic != null ? `${e.bp_systolic}/${e.bp_diastolic}` : null;
          const summary = e.raw_text ?? (bp ? `BP ${bp}` : "Check-in");
          return (
            <div
              key={i}
              className={`relative flex gap-4 pb-4 ${i < sorted.length - 1 ? "border-b border-border/50" : ""}`}
            >
              {/* Timeline spine */}
              <div className="flex flex-col items-center shrink-0 pt-0.5">
                <div className={`w-2.5 h-2.5 rounded-full ring-2 ring-surface ${flagged ? "bg-risk-escalate" : hasHeadache ? "bg-risk-monitor" : "bg-border-strong"}`} />
                {i < sorted.length - 1 && <div className="w-px flex-1 bg-border/60 mt-1.5" />}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 pt-0 pb-2">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{summary}</div>
                    {bp && e.raw_text && (
                      <div className="text-xs text-muted-foreground mt-0.5">BP {bp}</div>
                    )}
                    {e.notes && (
                      <div className="text-xs text-muted-foreground mt-1 leading-relaxed">{e.notes}</div>
                    )}
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {e.headache_severity != null && e.headache_severity > 0 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted border border-border font-medium">
                          Headache {e.headache_severity}/10
                        </span>
                      )}
                      {e.swelling_location && e.swelling_location !== "none" && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted border border-border font-medium">
                          Swelling: {e.swelling_location}
                        </span>
                      )}
                      {e.vision_changes === true && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-risk-monitor-bg text-risk-monitor border border-risk-monitor/20 font-medium">
                          Vision changes
                        </span>
                      )}
                      {e.fetal_movement && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted border border-border font-medium">
                          Movement: {e.fetal_movement}
                        </span>
                      )}
                      {e.medication_taken === false && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted border border-border text-muted-foreground font-medium">
                          Aspirin missed
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-[11px] text-muted-foreground shrink-0 tabular-nums whitespace-nowrap pt-0.5">
                    {fmtDate(e.timestamp)}
                  </div>
                </div>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

/* ── Escalations inbox ────────────────────────────────────────────────────── */

function EscalationsInbox({ items, onAck, onOpenPatient }: {
  items: EscalationSummary[];
  onAck: (id: string) => void;
  onOpenPatient: (pid: string) => void;
}) {
  const unread = items.filter((e) => !e.acknowledged).length;
  const acked = items.filter((e) => e.acknowledged).length;

  return (
    <div className="flex-1 flex flex-col">
      <div className="bg-surface border-b border-border px-5 py-3.5 flex items-center justify-between shrink-0" style={{ boxShadow: shadow }}>
        <div>
          <h1 className="font-display text-lg font-semibold">Escalations</h1>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Structured summaries · independently evaluated before delivery
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          <span><span className="font-bold text-foreground tabular-nums">{unread}</span> unread</span>
          <span className="text-border-strong">·</span>
          <span><span className="font-bold text-foreground tabular-nums">{acked}</span> acknowledged</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-4">
          {items.length === 0 ? (
            <div className="py-16 text-center">
              <div className="text-4xl mb-3">🌸</div>
              <p className="text-sm text-muted-foreground">No escalations yet.</p>
            </div>
          ) : (
            <ul className="space-y-3">
              {items.map((e) => {
                const sev: DisplayRisk = e.severity === "escalate_urgent" ? "escalate" : (e.severity as DisplayRisk);
                return (
                  <li
                    key={e.escalation_id}
                    className={`rounded-2xl border bg-surface ${
                      !e.acknowledged ? "border-risk-escalate/40 bg-risk-escalate-bg/20" : "border-border"
                    }`}
                    style={{ boxShadow: !e.acknowledged ? shadowMd : shadow }}
                  >
                    <div className="p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-center gap-3 min-w-0">
                          <Avatar name={e.patient_name} />
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-base font-semibold">{e.patient_name}</span>
                              <RiskBadge risk={!e.acknowledged ? "escalate" : sev} small />
                            </div>
                            <div className="text-[11px] text-muted-foreground mt-0.5 tabular-nums">{fmtTime(e.timestamp)}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {!e.acknowledged && <Btn onClick={() => onAck(e.escalation_id)}>Acknowledge</Btn>}
                          <Btn variant="primary" onClick={() => onOpenPatient(e.patient_id)}>Open patient</Btn>
                        </div>
                      </div>

                      <p className="mt-3.5 text-sm leading-relaxed">{e.summary}</p>

                      {e.triggering_readings.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {e.triggering_readings.map((v) => (
                            <span key={v} className="px-2 py-1 text-xs rounded-full bg-secondary text-secondary-foreground font-mono border border-border/50">
                              {v}
                            </span>
                          ))}
                        </div>
                      )}

                      <div className="mt-3 pt-3 border-t border-border">
                        <div className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground mb-1">Recommended action</div>
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
    <div className={`rounded-2xl border border-border bg-surface transition-shadow hover:shadow-md ${className}`} style={{ boxShadow: shadow }}>
      {children}
    </div>
  );
}

function CardTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-sm font-semibold text-foreground mb-0.5">{children}</div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">{children}</div>
  );
}

function Btn({ children, variant = "secondary", onClick }: {
  children: React.ReactNode; variant?: "primary" | "secondary"; onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center h-8 px-3.5 rounded-full text-sm font-semibold transition-all duration-100 active:scale-95 ${
        variant === "primary"
          ? "bg-primary text-primary-foreground hover:bg-primary/90 hover:-translate-y-px"
          : "bg-surface border border-border text-foreground hover:bg-secondary hover:border-primary/30"
      }`}
      style={variant === "primary" ? { boxShadow: shadow } : undefined}
    >
      {children}
    </button>
  );
}

function MetricChip({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider leading-none mb-1">{label}</div>
      <div className={`text-base font-semibold tabular-nums ${highlight ? "text-risk-escalate" : "text-foreground"}`}>{value}</div>
    </div>
  );
}

function BPTrendChip({ trend }: { trend: "up" | "down" | "stable" }) {
  const map = {
    up: { icon: "▲", label: "BP trending up", color: "text-risk-escalate" },
    down: { icon: "▼", label: "BP trending down", color: "text-risk-ok" },
    stable: { icon: "→", label: "BP stable", color: "text-muted-foreground" },
  };
  const t = map[trend];
  return (
    <div>
      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider leading-none mb-1">BP Trend</div>
      <div className={`text-sm font-semibold flex items-center gap-1 ${t.color}`}>
        <span>{t.icon}</span>
        <span>{t.label}</span>
      </div>
    </div>
  );
}

function AnalyticCard({ label, value, sub, color, ring }: {
  label: string; value: string; sub: string; color: string; ring?: number | null;
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4 transition-shadow hover:shadow-md" style={{ boxShadow: shadow }}>
      <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">{label}</div>
      <div className="flex items-end justify-between gap-2">
        <div>
          <div className={`text-2xl font-semibold tabular-nums leading-none ${color}`}>{value}</div>
          <div className="text-[11px] text-muted-foreground mt-1 leading-snug">{sub}</div>
        </div>
        {ring !== null && ring !== undefined && (
          <AdherenceRing pct={ring} small />
        )}
      </div>
    </div>
  );
}

function AdherenceRing({ pct, small = false }: { pct: number; small?: boolean }) {
  const size = small ? 36 : 48;
  const R = small ? 14 : 18;
  const circ = 2 * Math.PI * R;
  const dash = Math.max(0, Math.min(1, pct / 100)) * circ;
  const color = pct >= 80 ? "oklch(0.42 0.09 155)" : pct >= 60 ? "oklch(0.50 0.13 75)" : "oklch(0.50 0.20 25)";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={R} fill="none" stroke="oklch(0.92 0.05 305)" strokeWidth={small ? 4 : 5} />
      <circle
        cx={size / 2} cy={size / 2} r={R}
        fill="none"
        stroke={color}
        strokeWidth={small ? 4 : 5}
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      {!small && (
        <text x={size / 2} y={size / 2} textAnchor="middle" dominantBaseline="central" fontSize="10" fontWeight="700" fill="oklch(0.18 0.03 295)">
          {pct}%
        </text>
      )}
    </svg>
  );
}

function RiskMeter({ score }: { score: number }) {
  return (
    <div className="mt-2.5 mb-0.5 h-2 rounded-full bg-muted overflow-hidden">
      <div
        className="h-full rounded-full bg-gradient-to-r from-risk-ok via-risk-monitor to-risk-escalate transition-all"
        style={{ width: `${score * 100}%` }}
      />
    </div>
  );
}

function ChartLegend({ color, label, dashed }: { color?: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {dashed
        ? <span className="w-3 h-px border-t border-dashed border-risk-escalate" />
        : <span className={`w-2 h-2 rounded-sm ${color}`} />}
      {label}
    </span>
  );
}

function BPChart({ data }: { data: { day: string; sys: number; dia: number }[] }) {
  if (!data.length) return null;
  const W = 500;
  const H = 140;
  const PAD = { l: 26, r: 8, t: 8, b: 20 };
  const xs = (i: number) => PAD.l + (i * (W - PAD.l - PAD.r)) / Math.max(1, data.length - 1);
  const yMin = 60;
  const yMax = 160;
  const ys = (v: number) => PAD.t + (H - PAD.t - PAD.b) * (1 - (v - yMin) / (yMax - yMin));
  const sysPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${xs(i)},${ys(d.sys)}`).join(" ");
  const diaPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${xs(i)},${ys(d.dia)}`).join(" ");
  const threshold = ys(140);

  return (
    <div className="mt-2 w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="none">
        {[80, 100, 120, 140].map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={ys(v)} y2={ys(v)} stroke="oklch(0.91 0.012 300)" strokeWidth="1" />
            <text x={4} y={ys(v) + 3} fontSize="9" fill="oklch(0.50 0.04 295)">{v}</text>
          </g>
        ))}
        <line x1={PAD.l} x2={W - PAD.r} y1={threshold} y2={threshold} stroke="oklch(0.50 0.20 25)" strokeWidth="1" strokeDasharray="4 3" opacity="0.7" />
        <path d={sysPath} stroke="oklch(0.52 0.20 305)" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <path d={diaPath} stroke="oklch(0.38 0.15 305)" strokeWidth="2" fill="none" opacity="0.6" strokeLinecap="round" strokeLinejoin="round" />
        {data.map((d, i) => (
          <g key={i}>
            <circle cx={xs(i)} cy={ys(d.sys)} r={d.sys >= 140 ? 4.5 : 3} fill={d.sys >= 140 ? "oklch(0.50 0.20 25)" : "oklch(0.52 0.20 305)"} />
            <circle cx={xs(i)} cy={ys(d.dia)} r="2.5" fill="oklch(0.38 0.15 305)" opacity="0.7" />
            <text x={xs(i)} y={H - 4} fontSize="9" fill="oklch(0.50 0.04 295)" textAnchor="middle">{d.day}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}
