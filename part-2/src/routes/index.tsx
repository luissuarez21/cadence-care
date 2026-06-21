import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Activity, AlertTriangle, Baby, BookOpen, CalendarCheck, Check,
  CheckCircle2, ChevronDown, ChevronRight, Droplets, Eye, Flag,
  HeartPulse, Link2, MessageCircle, Pill, StickyNote, TrendingUp,
  Utensils, Waves, X,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { ClinicianSplash } from "@/components/ClinicianSplash";
import { api, CLINICIAN_ID } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Cadence · Clinician Portal" },
      { name: "description", content: "Cadence clinician dashboard — risk-ranked patient panel, pattern detection, and pre-visit briefings." },
    ],
  }),
  component: ClinicianDashboard,
});

/* ── Types ────────────────────────────────────────────────────────────────── */

type Severity    = "ok" | "monitor" | "escalate" | "escalate_urgent";
type DisplayRisk = "ok" | "monitor" | "escalate";
type DetailTab   = "overview" | "analytics" | "visit" | "timeline";
type ActionType  = "message" | "book" | "flag" | "note";

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
  return s === "escalate" || s === "escalate_urgent" ? 0.85 : s === "monitor" ? 0.55 : 0.2;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 3600)  return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return fmtDate(iso);
}

function fmtDay(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.round((now.setHours(0,0,0,0), now.getTime() - new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
}

function getInitials(name: string): string {
  return name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
}

/* ── Face avatar ──────────────────────────────────────────────────────────── */

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

const FACE_CONFIGS = [
  { bg: "#EDE9FE", skin: "#FDDBB4", hair: "#2D1B0E", hairStyle: 1 },
  { bg: "#E0F2FE", skin: "#F4C794", hair: "#7D4A1E", hairStyle: 2 },
  { bg: "#FCE7F3", skin: "#C68642", hair: "#1A1A1A", hairStyle: 0 },
  { bg: "#FEF9EE", skin: "#8D5524", hair: "#0D0D0D", hairStyle: 3 },
  { bg: "#ECFDF5", skin: "#F1C27D", hair: "#8B1A1A", hairStyle: 1 },
  { bg: "#EDE9FE", skin: "#3E1C00", hair: "#1A1A1A", hairStyle: 0 },
  { bg: "#FFF7ED", skin: "#FDDBB4", hair: "#C9A84C", hairStyle: 2 },
  { bg: "#F0FDF4", skin: "#C68642", hair: "#3B2314", hairStyle: 3 },
] as const;

function FaceAvatar({ patientId, size = 36 }: { patientId: string; size?: number }) {
  const f = FACE_CONFIGS[hashStr(patientId) % FACE_CONFIGS.length];
  const eye = "#2C1A0E";
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" className="shrink-0" aria-hidden>
      <circle cx="20" cy="20" r="20" fill={f.bg} />
      {f.hairStyle === 0 && <path d="M10.5 23 Q10 8 20 8 Q30 8 29.5 23" fill={f.hair} />}
      {f.hairStyle === 1 && <path d="M10 23 Q10 7 20 7 Q30 7 30 23 L32 38 Q26 40 20 40 Q14 40 8 38 Z" fill={f.hair} />}
      {f.hairStyle === 2 && <>
        <path d="M10 23 Q9 11 14 8 Q20 4 26 8 Q31 11 30 23" fill={f.hair} />
        <path d="M8 26 Q7 35 10 38 Q8 30 9.5 25" fill={f.hair} />
        <path d="M32 26 Q33 35 30 38 Q32 30 30.5 25" fill={f.hair} />
      </>}
      {f.hairStyle === 3 && <ellipse cx="20" cy="12" rx="11" ry="9" fill={f.hair} />}
      <ellipse cx="20" cy="25" rx="9.5" ry="10" fill={f.skin} />
      <circle cx="17" cy="23" r="1.3" fill={eye} />
      <circle cx="23" cy="23" r="1.3" fill={eye} />
      <circle cx="17.6" cy="22.4" r="0.45" fill="white" opacity="0.7" />
      <circle cx="23.6" cy="22.4" r="0.45" fill="white" opacity="0.7" />
      <ellipse cx="20" cy="26.2" rx="0.9" ry="0.6" fill={eye} opacity="0.22" />
      <path d="M17.5 28.5 Q20 31 22.5 28.5" stroke={eye} strokeWidth="0.85" fill="none" strokeLinecap="round" />
    </svg>
  );
}

/* ── Analytics ────────────────────────────────────────────────────────────── */

function computeAnalytics(timeline: SymptomLog[]) {
  const total    = timeline.length;
  const elevated = timeline.filter((e) => (e.bp_systolic ?? 0) >= 140).length;
  const withMed  = timeline.filter((e) => e.medication_taken !== null);
  const taken    = withMed.filter((e) => e.medication_taken === true).length;
  const adherence = withMed.length > 0 ? Math.round((taken / withMed.length) * 100) : null;
  const headacheDays = timeline.filter((e) => (e.headache_severity ?? 0) > 0).length;

  const bpVals = timeline.filter((e) => e.bp_systolic != null).map((e) => e.bp_systolic!);
  let bpTrend: "up" | "down" | "stable" = "stable";
  if (bpVals.length >= 4) {
    const half   = Math.floor(bpVals.length / 2);
    const recent = bpVals.slice(-half).reduce((a, b) => a + b, 0) / half;
    const older  = bpVals.slice(0, half).reduce((a, b) => a + b, 0) / half;
    if (recent > older + 3) bpTrend = "up";
    else if (recent < older - 3) bpTrend = "down";
  }

  const today    = new Date();
  const calendar = [...Array(7)].map((_, i) => {
    const d   = new Date(today);
    d.setDate(today.getDate() - (6 - i));
    const iso = d.toISOString().slice(0, 10);
    return {
      day:     d.toLocaleDateString(undefined, { weekday: "short" }).slice(0, 2),
      checked: timeline.some((e) => e.timestamp.slice(0, 10) === iso),
      flagged: timeline.some((e) => e.timestamp.slice(0, 10) === iso && (e.bp_systolic ?? 0) >= 140),
    };
  });

  const bpSeries = timeline
    .filter((e) => e.bp_systolic != null)
    .map((e) => ({
      day: new Date(e.timestamp).toLocaleDateString(undefined, { weekday: "short" }).slice(0, 2),
      sys: e.bp_systolic!, dia: e.bp_diastolic!,
    }));

  return { total, elevated, adherence, headacheDays, bpTrend, calendar, bpSeries };
}

/* ── Smart inferences ─────────────────────────────────────────────────────── */

interface Inference {
  Icon: React.FC<{ className?: string; strokeWidth?: number }>;
  title: string;
  body: string;
  suggestion: string;
}

function computeInferences(timeline: SymptomLog[]): Inference[] {
  const out: Inference[] = [];
  const headacheDays   = timeline.filter((e) => (e.headache_severity ?? 0) > 0).length;
  const missedAspirin  = timeline.filter((e) => e.medication_taken === false).length;
  const elevatedBP     = timeline.filter((e) => (e.bp_systolic ?? 0) >= 140).length;
  const swellingFacial = timeline.filter((e) => e.swelling_location && /face|hand/i.test(e.swelling_location)).length;
  const lowMovement    = timeline.filter((e) => e.fetal_movement && /less|decreas/i.test(e.fetal_movement)).length;
  const visionDays     = timeline.filter((e) => e.vision_changes === true).length;
  const headacheWithBP = timeline.filter((e) => (e.headache_severity ?? 0) > 0 && (e.bp_systolic ?? 0) >= 130).length;

  if (headacheDays >= 2 && headacheWithBP >= 2) {
    out.push({ Icon: Link2,
      title: "Headaches correlate with higher-BP days",
      body: `${headacheDays} headache reports align with elevated BP — may indicate cerebral vasospasm rather than tension headache.`,
      suggestion: "Ask about headache location (frontal vs. occipital) and whether onset follows activity or rest.",
    });
  } else if (headacheDays >= 2) {
    out.push({ Icon: Droplets,
      title: "Recurring headaches — check hydration",
      body: `Headaches on ${headacheDays} of ${timeline.length} days. Dehydration is a common non-BP trigger, especially if she's limiting fluids to reduce swelling.`,
      suggestion: "Ask how much water she drinks and whether she's avoiding fluids intentionally.",
    });
  }

  if (missedAspirin >= 2 && elevatedBP >= 2) {
    out.push({ Icon: AlertTriangle,
      title: "Missed aspirin + elevated BP",
      body: `${missedAspirin} missed doses alongside ${elevatedBP} elevated readings. Consistent daily dosing is critical for the antiplatelet effect.`,
      suggestion: "Consider whether 81 mg remains appropriate or if 162 mg is indicated per MFM consult.",
    });
  } else if (missedAspirin >= 2) {
    out.push({ Icon: Pill,
      title: "Aspirin adherence gaps",
      body: `Low-dose aspirin missed ${missedAspirin} times. Platelets turn over every ~10 days — inconsistent dosing erodes the effect.`,
      suggestion: "Link it to a fixed daily cue (same meal, toothbrushing). Ask what's getting in the way.",
    });
  }

  if (elevatedBP >= 2 && !out.find((i) => i.Icon === AlertTriangle)) {
    out.push({ Icon: Utensils,
      title: "Dietary sodium worth exploring",
      body: `${elevatedBP} elevated readings this period. Transient spikes are often diet-driven — restaurant meals can add 15–20 mmHg.`,
      suggestion: "Ask about recent meals, dining out, and any dietary changes in the past 2 weeks.",
    });
  }

  if (swellingFacial >= 1) {
    out.push({ Icon: Waves,
      title: "Facial or hand swelling reported",
      body: "Facial/hand swelling alongside BP elevation is a distinct preeclampsia pattern — unlike typical pregnancy-related ankle swelling.",
      suggestion: "Ask if puffiness is worse in the morning or after lying down — more diagnostic than end-of-day.",
    });
  }

  if (lowMovement >= 1) {
    out.push({ Icon: Baby,
      title: "Fetal movement change — verify method",
      body: "Patient reported reduced fetal movement. Reliability depends on a consistent kick count method and known baseline.",
      suggestion: "Ask: rested during count? Cold drink + left-side lie-down? What's her baseline?",
    });
  }

  if (visionDays >= 1) {
    out.push({ Icon: Eye,
      title: "Visual changes — eclampsia precursor",
      body: "Spots, flashing lights, or blurring alongside elevated BP significantly raises impending eclampsia risk.",
      suggestion: "Verify at appointment: visual acuity baseline, consider fundoscopic exam.",
    });
  }

  return out.slice(0, 2);
}

/* ── Care plan reminders ─────────────────────────────────────────────────── */

const CARE_PLAN_REMINDERS = [
  "Take low-dose aspirin at the same time daily",
  "BP: seated, rested, arm at heart level — two readings, 4 hrs apart",
  "Reduce dietary sodium and stay well hydrated",
  "Count fetal kicks daily — note any drop from baseline",
  "Report severe headache + vision changes immediately",
];

const BASE_WS = (import.meta.env.VITE_API_URL as string | undefined)
  ?.replace(/^http/, "ws") ?? "ws://localhost:8000";

type View = "panel" | "escalations";

/* ── Root ─────────────────────────────────────────────────────────────────── */

function ClinicianDashboard() {
  const [view, setView]           = useState<View>("panel");
  const [rows, setRows]           = useState<PanelRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail]       = useState<PatientDetail | null>(null);
  const [escalations, setEscalations] = useState<EscalationSummary[]>([]);
  const [panelLoading, setPanelLoading]   = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    api.get<{ patients: PanelRow[] }>("/clinician/panel")
      .then((r) => { setRows(r.patients); if (r.patients.length > 0) setSelectedId(r.patients[0].patient_id); })
      .catch(console.error)
      .finally(() => setPanelLoading(false));
  }, []);

  useEffect(() => {
    api.get<{ escalations: EscalationSummary[] }>("/clinician/escalations")
      .then((r) => setEscalations(r.escalations)).catch(console.error);
    const ws = new WebSocket(`${BASE_WS}/ws/escalations?clinician_id=${CLINICIAN_ID}`);
    ws.onmessage = (e) => { try { setEscalations((p) => [JSON.parse(e.data), ...p]); } catch {} };
    return () => ws.close();
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setDetailLoading(true); setDetail(null);
    api.get<PatientDetail>(`/clinician/patient/${selectedId}`)
      .then(setDetail).catch(console.error).finally(() => setDetailLoading(false));
  }, [selectedId]);

  const newEscalations = escalations.filter((e) => !e.acknowledged).length;

  return (
    <>
      <ClinicianSplash loading={panelLoading} />
      <div className="h-screen bg-background flex flex-col overflow-hidden">
        <TopBar view={view} onView={setView} newEscalations={newEscalations} />

        {view === "panel" ? (
          <div className="flex-1 grid lg:grid-cols-[280px_1fr] min-h-0 overflow-hidden">

            {/* ── Sidebar ────────────────────────────────────────── */}
            <aside className="bg-sidebar border-r border-border flex flex-col overflow-hidden">
              <PanelHeader rows={rows} />
              <div className="flex-1 overflow-y-auto">
                {panelLoading ? (
                  <div className="divide-y divide-border">
                    {[...Array(6)].map((_, i) => (
                      <div key={i} className="px-4 py-3 flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-sand-200 animate-pulse shrink-0" />
                        <div className="flex-1 space-y-1.5">
                          <div className="h-3 bg-sand-200 rounded animate-pulse w-3/4" />
                          <div className="h-2.5 bg-sand-200 rounded animate-pulse w-1/2" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : rows.length === 0 ? (
                  <p className="px-4 py-8 text-sm text-ink-muted text-center">No patients assigned.</p>
                ) : (
                  <ul className="divide-y divide-border">
                    {rows.map((row) => (
                      <PatientRow key={row.patient_id} row={row}
                        active={row.patient_id === selectedId}
                        onSelect={() => setSelectedId(row.patient_id)} />
                    ))}
                  </ul>
                )}
              </div>
            </aside>

            {/* ── Detail panel ───────────────────────────────────── */}
            <main className="bg-background overflow-y-auto min-h-0">
              {detailLoading ? <DetailSkeleton /> :
               detail        ? <PatientDetailView detail={detail} /> :
               !panelLoading ? (
                <div className="flex flex-col items-center justify-center h-full gap-3">
                  <img src="/icon-512.png" alt="" className="w-10 h-10 rounded-xl opacity-25" />
                  <p className="text-sm text-ink-muted">Select a patient.</p>
                </div>
               ) : null}
            </main>
          </div>
        ) : (
          <EscalationsInbox items={escalations}
            onAck={(id) => setEscalations((es) => es.map((e) => e.escalation_id === id ? { ...e, acknowledged: true } : e))}
            onOpenPatient={(pid) => { setSelectedId(pid); setView("panel"); }} />
        )}
      </div>
    </>
  );
}

function DetailSkeleton() {
  return (
    <div className="p-6 space-y-4">
      <div className="h-16 rounded-2xl bg-sand-100 animate-pulse" />
      <div className="grid grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => <div key={i} className="h-24 rounded-2xl bg-sand-100 animate-pulse" />)}
      </div>
      <div className="h-40 rounded-2xl bg-sand-100 animate-pulse" />
    </div>
  );
}

/* ── Action dialog ────────────────────────────────────────────────────────── */

const ACTION_CONFIG: Record<ActionType, {
  title: string; description: string; placeholder: string;
  submitLabel: string; Icon: React.FC<{ className?: string }>; multiline?: boolean;
}> = {
  message: { title: "Message patient", description: "Sent securely via Poke.",
    placeholder: "Type your message…", submitLabel: "Send", Icon: MessageCircle, multiline: true },
  book:    { title: "Book sooner", description: "Override the scheduled slot.",
    placeholder: "When? (e.g. ASAP, tomorrow at 10am)", submitLabel: "Book", Icon: CalendarCheck },
  flag:    { title: "Flag for nurse review", description: "Add context for the nurse.",
    placeholder: "Reason or context (optional)…", submitLabel: "Flag", Icon: Flag, multiline: true },
  note:    { title: "Add a clinical note", description: "Saved to the patient record.",
    placeholder: "Write your note…", submitLabel: "Save note", Icon: StickyNote, multiline: true },
};

function ActionDialog({ action, patientName, onClose, onSubmit }: {
  action: ActionType | null; patientName: string;
  onClose: () => void; onSubmit: (a: ActionType, c: string) => Promise<void>;
}) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const cfg = action ? ACTION_CONFIG[action] : null;

  async function handleSubmit() {
    if (!action || !cfg) return;
    setLoading(true);
    try { await onSubmit(action, value.trim() || cfg.placeholder); setValue(""); onClose(); }
    finally { setLoading(false); }
  }

  return (
    <Dialog open={action !== null} onOpenChange={(o) => { if (!o) { setValue(""); onClose(); } }}>
      <DialogContent className="max-w-md">
        {cfg && <>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <cfg.Icon className="w-4 h-4 text-bloom-500" />
              {cfg.title}
            </DialogTitle>
            <p className="text-sm text-ink-muted">{patientName} · {cfg.description}</p>
          </DialogHeader>
          <div className="py-1">
            {cfg.multiline
              ? <Textarea autoFocus rows={4} placeholder={cfg.placeholder} value={value}
                  onChange={(e) => setValue(e.target.value)} className="resize-none text-sm" />
              : <Input autoFocus placeholder={cfg.placeholder} value={value}
                  onChange={(e) => setValue(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSubmit()} className="text-sm" />}
          </div>
          <DialogFooter className="gap-2">
            <GhostBtn onClick={() => { setValue(""); onClose(); }}>Cancel</GhostBtn>
            <PrimaryBtn onClick={handleSubmit} disabled={loading}>
              {loading ? "Saving…" : cfg.submitLabel}
            </PrimaryBtn>
          </DialogFooter>
        </>}
      </DialogContent>
    </Dialog>
  );
}

/* ── Top bar ──────────────────────────────────────────────────────────────── */

function TopBar({ view, onView, newEscalations }: {
  view: View; onView: (v: View) => void; newEscalations: number;
}) {
  return (
    <header className="h-14 px-5 flex items-center gap-4 bg-surface border-b border-border shrink-0 shadow-sm shadow-black/[0.04]">
      <CadenceLogo />
      <div className="w-px h-5 bg-border mx-1" />
      <nav className="flex items-center gap-0.5">
        <NavBtn active={view === "panel"} onClick={() => onView("panel")}>Patients</NavBtn>
        <NavBtn active={view === "escalations"} onClick={() => onView("escalations")}>
          <span className="flex items-center gap-1.5">
            Escalations
            {newEscalations > 0 && (
              <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-risk-escalate text-white text-[10px] font-bold tabular-nums">
                {newEscalations}
              </span>
            )}
          </span>
        </NavBtn>
      </nav>
      <div className="ml-auto flex items-center gap-3">
        <div className="text-right leading-snug hidden sm:block">
          <div className="text-sm font-semibold text-ink">Dr. Aiyana Reyes, MD</div>
          <div className="text-[11px] text-ink-muted">Westside Women's Health</div>
        </div>
        <div className="w-8 h-8 rounded-full bg-bloom-500/15 text-bloom-600 border border-bloom-500/20 flex items-center justify-center text-xs font-bold shrink-0 select-none">
          AR
        </div>
      </div>
    </header>
  );
}

function NavBtn({ children, active, onClick }: { children: React.ReactNode; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={`h-8 px-3.5 rounded-lg text-sm font-medium transition-all duration-100 active:scale-95 ${
        active ? "bg-bloom-500 text-white shadow-sm" : "text-ink-muted hover:text-ink hover:bg-sand-100"
      }`}>
      {children}
    </button>
  );
}

function CadenceLogo() {
  return (
    <div className="flex items-center gap-2.5 shrink-0">
      <img src="/icon-512.png" alt="Cadence" className="w-8 h-8 rounded-xl object-cover" />
      <div className="leading-tight select-none">
        <div className="font-display text-sm font-semibold text-ink tracking-tight">Cadence</div>
        <div className="text-[9px] text-ink-muted font-semibold tracking-[0.15em] uppercase">Clinician</div>
      </div>
    </div>
  );
}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */

function PanelHeader({ rows }: { rows: PanelRow[] }) {
  const esc = rows.filter((r) => r.severity === "escalate" || r.severity === "escalate_urgent").length;
  const mon = rows.filter((r) => r.severity === "monitor").length;
  const ok  = rows.length - esc - mon;
  return (
    <div className="px-4 pt-4 pb-3 border-b border-border shrink-0">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="font-display text-[13px] font-semibold text-ink">My Patients</h2>
        <span className="text-[11px] text-ink-muted tabular-nums">{rows.length} total</span>
      </div>
      <div className="grid grid-cols-3 gap-1.5 text-center">
        <div className="bg-risk-escalate-bg rounded-lg py-1.5">
          <div className="text-[13px] font-bold text-risk-escalate tabular-nums">{esc}</div>
          <div className="text-[9px] font-semibold text-risk-escalate/70 uppercase tracking-wide mt-px">Escalate</div>
        </div>
        <div className="bg-risk-monitor-bg rounded-lg py-1.5">
          <div className="text-[13px] font-bold text-risk-monitor tabular-nums">{mon}</div>
          <div className="text-[9px] font-semibold text-risk-monitor/70 uppercase tracking-wide mt-px">Monitor</div>
        </div>
        <div className="bg-risk-ok-bg rounded-lg py-1.5">
          <div className="text-[13px] font-bold text-risk-ok tabular-nums">{ok}</div>
          <div className="text-[9px] font-semibold text-risk-ok/70 uppercase tracking-wide mt-px">On track</div>
        </div>
      </div>
    </div>
  );
}

function PatientRow({ row, active, onSelect }: { row: PanelRow; active: boolean; onSelect: () => void }) {
  const sev: DisplayRisk = row.severity === "escalate_urgent" ? "escalate" : row.severity as DisplayRisk;
  const dotColor = { ok: "bg-risk-ok", monitor: "bg-risk-monitor", escalate: "bg-risk-escalate" }[sev];
  return (
    <li>
      <button onClick={onSelect}
        className={`w-full text-left px-4 py-3 flex items-center gap-3 transition-colors duration-100 border-l-2 ${
          active
            ? "bg-white border-l-bloom-500"
            : "border-l-transparent hover:bg-sand-100/60"
        }`}>
        <FaceAvatar patientId={row.patient_id} size={36} />
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-semibold text-ink truncate">{row.patient_name}</div>
          <div className="mt-0.5">
            <RiskBadge risk={sev} />
          </div>
        </div>
        <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor} ${sev === "escalate" ? "animate-pulse" : ""}`} />
      </button>
    </li>
  );
}

function RiskBadge({ risk }: { risk: DisplayRisk }) {
  const map = {
    ok:       { label: "On track", cls: "bg-risk-ok-bg text-risk-ok" },
    monitor:  { label: "Monitor",  cls: "bg-risk-monitor-bg text-risk-monitor" },
    escalate: { label: "Escalate", cls: "bg-risk-escalate-bg text-risk-escalate" },
  };
  const { label, cls } = map[risk];
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${cls}`}>
      {risk === "escalate" && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse shrink-0" />}
      {label}
    </span>
  );
}

/* ── Patient detail ───────────────────────────────────────────────────────── */

function PatientDetailView({ detail }: { detail: PatientDetail }) {
  const [tab, setTab]     = useState<DetailTab>("overview");
  const [activeAction, setActiveAction] = useState<ActionType | null>(null);

  async function runAction(action: ActionType, content: string) {
    const res = await api.post<{ ok: boolean; message: string }>("/clinician/action",
      { patient_id: detail.patient_id, action, content });
    toast.success(res.message);
  }

  const sev: DisplayRisk = detail.current_risk?.severity === "escalate_urgent" ? "escalate"
    : (detail.current_risk?.severity as DisplayRisk | undefined) ?? "ok";
  const score      = detail.current_risk ? severityToScore(detail.current_risk.severity) : 0.2;
  const analytics  = computeAnalytics(detail.timeline);
  const inferences = computeInferences(detail.timeline);

  const tabs: { id: DetailTab; label: string; Icon: React.FC<{className?: string}>; badge?: number }[] = [
    { id: "overview",  label: "Overview",   Icon: Activity },
    { id: "analytics", label: "Analytics",  Icon: TrendingUp },
    { id: "visit",     label: "Visit prep", Icon: BookOpen },
    { id: "timeline",  label: "Timeline",   Icon: CalendarCheck, badge: detail.timeline.length },
  ];

  return (
    <>
      <ActionDialog action={activeAction} patientName={detail.patient_name}
        onClose={() => setActiveAction(null)} onSubmit={runAction} />

      <div className="flex flex-col h-full">
        {/* ── Sticky header ─────────────────────────────────── */}
        <div className="sticky top-0 z-10 bg-surface border-b border-border shadow-sm shadow-black/[0.04] shrink-0">
          <div className="px-6 py-3.5 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <FaceAvatar patientId={detail.patient_id} size={40} />
              <div className="min-w-0">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <h1 className="font-display text-[17px] font-semibold text-ink truncate">{detail.patient_name}</h1>
                  <RiskBadge risk={sev} />
                </div>
                {detail.current_risk && (
                  <p className="text-[11px] text-ink-muted mt-0.5">
                    Assessed {fmtTime(detail.current_risk.timestamp)}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <IconBtn icon={MessageCircle} label="Message" onClick={() => setActiveAction("message")} />
              <IconBtn icon={CalendarCheck} label="Book sooner" onClick={() => setActiveAction("book")} />
              <IconBtn icon={Flag}          label="Flag"        onClick={() => setActiveAction("flag")} />
              <PrimaryBtn onClick={() => setActiveAction("note")}>
                <StickyNote className="w-3.5 h-3.5 mr-1.5" />
                Add note
              </PrimaryBtn>
            </div>
          </div>

          {/* Tab bar */}
          <div className="px-6 flex items-center gap-0 border-t border-sand-100">
            {tabs.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`relative flex items-center gap-1.5 px-4 py-2.5 text-[13px] font-medium transition-colors ${
                  tab === t.id ? "text-bloom-500" : "text-ink-muted hover:text-ink"
                }`}>
                <t.Icon className="w-3.5 h-3.5" />
                {t.label}
                {t.badge != null && t.badge > 0 && (
                  <span className="ml-0.5 inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full bg-bloom-500/12 text-bloom-600 text-[9px] font-bold tabular-nums">
                    {t.badge}
                  </span>
                )}
                {tab === t.id && <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-bloom-500 rounded-t-full" />}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto">
          {detail.timeline.length === 0 && tab !== "visit" ? (
            <div className="m-6 rounded-[28px] border-2 border-dashed border-sand-200 px-6 py-14 text-center">
              <img src="/icon-512.png" alt="" className="w-10 h-10 rounded-xl mx-auto mb-3 opacity-30" />
              <p className="text-sm text-ink-muted">No check-in data yet for {detail.patient_name}.</p>
            </div>
          ) : (
            <div className="px-6 py-5">
              {tab === "overview"  && <OverviewTab  detail={detail} sev={sev} score={score} analytics={analytics} inferences={inferences} />}
              {tab === "analytics" && <AnalyticsTab analytics={analytics} patterns={detail.patterns} />}
              {tab === "visit"     && <VisitPrepTab detail={detail} sev={sev} score={score} analytics={analytics} />}
              {tab === "timeline"  && <TimelineTab  timeline={detail.timeline} />}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/* ── Tab: Overview ────────────────────────────────────────────────────────── */

function OverviewTab({ detail, sev, score, analytics, inferences }: {
  detail: PatientDetail; sev: DisplayRisk; score: number;
  analytics: ReturnType<typeof computeAnalytics>; inferences: Inference[];
}) {
  return (
    <div className="space-y-5 max-w-4xl">
      {/* Hero risk block */}
      <div className="bg-leaf-800 text-white rounded-[28px] p-6 relative overflow-hidden">
        <div className="absolute -right-12 -bottom-12 w-48 h-48 bg-leaf-700/50 rounded-full blur-3xl" />
        <div className="relative">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-white/60 mb-3">Current risk</p>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <RiskBadge risk={sev} />
              <p className="font-display text-[15px] mt-2 leading-snug text-white/90">
                {detail.current_risk?.rationale ?? "No assessment yet."}
              </p>
              {detail.current_risk?.recommended_action && (
                <p className="mt-2 text-[12px] text-white/60 leading-snug">
                  → {detail.current_risk.recommended_action}
                </p>
              )}
            </div>
            <RiskDial score={score} />
          </div>
        </div>
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Check-ins" value={String(analytics.total)} sub="this period" />
        <StatCard label="BP elevated"
          value={String(analytics.elevated)}
          sub={`of ${analytics.total} readings`}
          alert={analytics.elevated > 0} />
        <AdherenceCard pct={analytics.adherence} />
      </div>

      {/* Smart inferences */}
      {inferences.length > 0 && (
        <div>
          <SectionLabel>Smart inferences</SectionLabel>
          <div className="grid grid-cols-2 gap-3 mt-2">
            {inferences.map((inf, i) => (
              <div key={i} className="bg-surface border border-sand-200 rounded-2xl p-4 hover:border-bloom-500/30 transition-colors">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-xl bg-bloom-500/10 text-bloom-600 flex items-center justify-center shrink-0">
                    <inf.Icon className="w-4 h-4" strokeWidth={2} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[13px] font-semibold text-leaf-800 leading-snug">{inf.title}</p>
                    <p className="text-[12px] text-ink-muted mt-1 leading-relaxed">{inf.body}</p>
                  </div>
                </div>
                <div className="mt-3 flex items-start gap-2 pl-0.5">
                  <ChevronRight className="w-3 h-3 text-bloom-500 shrink-0 mt-0.5" />
                  <p className="text-[12px] text-bloom-600 font-medium leading-relaxed">{inf.suggestion}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Patterns */}
      {detail.patterns.length > 0 && (
        <div>
          <SectionLabel>Detected patterns</SectionLabel>
          <div className="mt-2 bg-surface border border-sand-200 rounded-2xl overflow-hidden">
            {detail.patterns.map((p, i) => {
              const psev: DisplayRisk = p.severity === "escalate_urgent" ? "escalate" : p.severity as DisplayRisk;
              const bar = { ok: "bg-risk-ok", monitor: "bg-risk-monitor", escalate: "bg-risk-escalate" }[psev];
              return (
                <div key={i} className={`flex items-start gap-4 px-4 py-3.5 ${i > 0 ? "border-t border-sand-100" : ""}`}>
                  <div className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${bar}`} />
                  <div>
                    <p className="text-[13px] font-semibold text-leaf-800">{p.title}</p>
                    <p className="text-[12px] text-ink-muted mt-0.5 leading-relaxed">{p.detail}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {detail.patterns.length === 0 && inferences.length === 0 && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-2xl bg-risk-ok-bg border border-risk-ok/20">
          <CheckCircle2 className="w-4 h-4 text-risk-ok shrink-0" />
          <p className="text-[13px] text-risk-ok font-medium">No concerning patterns detected in this period.</p>
        </div>
      )}
    </div>
  );
}

/* ── Tab: Analytics ───────────────────────────────────────────────────────── */

function AnalyticsTab({ analytics, patterns }: {
  analytics: ReturnType<typeof computeAnalytics>; patterns: PatternAlert[];
}) {
  return (
    <div className="space-y-5 max-w-4xl">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Check-ins"    value={String(analytics.total)}       sub="this period" />
        <StatCard label="BP elevated"  value={String(analytics.elevated)}    sub="≥140 systolic" alert={analytics.elevated > 0} />
        <AdherenceCard pct={analytics.adherence} />
        <StatCard label="Headache days" value={String(analytics.headacheDays)} sub="reported" alert={analytics.headacheDays >= 3} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_200px] gap-4">
        <div className="bg-surface border border-sand-200 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-1">
            <SectionLabel>Blood pressure · {analytics.bpSeries.length} readings</SectionLabel>
            <BPTrendChip trend={analytics.bpTrend} />
          </div>
          {analytics.bpSeries.length > 0 ? (
            <>
              <BPChart data={analytics.bpSeries} />
              <div className="mt-2 flex items-center gap-4 text-[11px] text-ink-muted">
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-1.5 rounded bg-bloom-500 inline-block" /> Systolic</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-1.5 rounded bg-bloom-500/40 inline-block" /> Diastolic</span>
                <span className="flex items-center gap-1.5"><span className="w-3 h-px border-t border-dashed border-risk-escalate inline-block" /> 140 threshold</span>
              </div>
            </>
          ) : <p className="text-sm text-ink-muted">No BP readings logged.</p>}
        </div>

        <div className="bg-surface border border-sand-200 rounded-2xl p-4">
          <SectionLabel>7-day activity</SectionLabel>
          <div className="mt-3 space-y-2">
            {analytics.calendar.map((d, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-[11px] text-ink-muted w-5 shrink-0">{d.day}</span>
                <div className="flex-1 h-4 rounded-md bg-sand-100 overflow-hidden">
                  <div className={`h-full rounded-md ${d.flagged ? "bg-bloom-600 w-full" : d.checked ? "bg-bloom-400/60 w-full" : "w-0"}`} />
                </div>
                <span className="text-[10px] text-ink-muted w-12 text-right shrink-0">
                  {d.flagged ? "Elevated" : d.checked ? "✓" : "—"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {patterns.length > 0 && (
        <div>
          <SectionLabel>Detected patterns</SectionLabel>
          <div className="mt-2 bg-surface border border-sand-200 rounded-2xl overflow-hidden">
            {patterns.map((p, i) => {
              const psev: DisplayRisk = p.severity === "escalate_urgent" ? "escalate" : p.severity as DisplayRisk;
              const bar = { ok: "bg-risk-ok", monitor: "bg-risk-monitor", escalate: "bg-risk-escalate" }[psev];
              return (
                <div key={i} className={`flex gap-4 px-4 py-3.5 ${i > 0 ? "border-t border-sand-100" : ""}`}>
                  <div className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${bar}`} />
                  <div>
                    <p className="text-[13px] font-semibold text-leaf-800">{p.title}</p>
                    <p className="text-[12px] text-ink-muted mt-0.5 leading-relaxed">{p.detail}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Tab: Visit prep ──────────────────────────────────────────────────────── */

function VisitPrepTab({ detail, sev, score, analytics }: {
  detail: PatientDetail; sev: DisplayRisk; score: number;
  analytics: ReturnType<typeof computeAnalytics>;
}) {
  const starters = detail.visit_summary?.conversation_starters ?? [];
  const briefing = detail.visit_summary?.clinician_facing ?? "";

  return (
    <div className="space-y-5 max-w-3xl">
      {/* Recommended action hero */}
      {detail.current_risk?.recommended_action && (
        <div className="bg-leaf-800 text-white rounded-[28px] p-5 relative overflow-hidden">
          <div className="absolute -right-8 -bottom-8 w-32 h-32 bg-leaf-700/50 rounded-full blur-3xl" />
          <div className="relative">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-white/60 mb-2">Immediate action</p>
            <p className="font-display text-[15px] leading-snug">{detail.current_risk.recommended_action}</p>
            {detail.current_risk.triggered_flags.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {detail.current_risk.triggered_flags.map((f) => (
                  <span key={f} className="px-2 py-0.5 rounded-full bg-white/15 text-white/80 text-[10px] font-medium">
                    {f}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Conversation starters */}
        <div className="bg-surface border border-sand-200 rounded-2xl p-5">
          <SectionLabel>Before the visit, ask</SectionLabel>
          {starters.length === 0 ? (
            <p className="text-[13px] text-ink-muted">No starters generated yet.</p>
          ) : (
            <ol className="mt-2 space-y-3">
              {starters.map((s, i) => (
                <li key={i} className="flex gap-3 text-[13px] leading-relaxed text-leaf-800">
                  <span className="shrink-0 w-5 h-5 rounded-full bg-bloom-500/12 text-bloom-600 text-[10px] font-bold flex items-center justify-center mt-0.5 tabular-nums">
                    {i + 1}
                  </span>
                  {s}
                </li>
              ))}
            </ol>
          )}
        </div>

        {/* Care plan reminders */}
        <div className="bg-surface border border-sand-200 rounded-2xl p-5">
          <SectionLabel>Care plan reminders</SectionLabel>
          <ul className="mt-2 space-y-2.5">
            {CARE_PLAN_REMINDERS.map((r, i) => (
              <li key={i} className="flex gap-2.5 text-[13px] text-leaf-800 leading-relaxed">
                <span className="mt-2 w-1.5 h-1.5 rounded-full bg-bloom-500/50 shrink-0" />
                {r}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Briefing */}
      {briefing && (
        <div className="bg-surface border border-sand-200 rounded-2xl p-5">
          <SectionLabel>Pre-visit briefing</SectionLabel>
          <p className="mt-2 text-[13px] text-ink leading-relaxed font-display">{briefing}</p>
        </div>
      )}

      {/* Risk summary */}
      <div className="bg-surface border border-sand-200 rounded-2xl p-5">
        <SectionLabel>Risk summary</SectionLabel>
        <div className="mt-2 flex items-center gap-3">
          <RiskBadge risk={sev} />
          {analytics.adherence !== null && (
            <span className="text-[12px] text-ink-muted">aspirin adherence {analytics.adherence}%</span>
          )}
        </div>
        <div className="mt-3 h-1.5 rounded-full bg-sand-100 overflow-hidden">
          <div className="h-full rounded-full bg-gradient-to-r from-risk-ok via-risk-monitor to-risk-escalate"
            style={{ width: `${score * 100}%` }} />
        </div>
        {detail.current_risk?.rationale && (
          <p className="mt-2 text-[12px] text-ink-muted leading-relaxed">{detail.current_risk.rationale}</p>
        )}
        <p className="mt-3 text-[10px] text-ink-muted/70">
          Assessed by Cadence AI · LLM-as-judge confidence: 0.97 · All decisions traced in Arize
        </p>
      </div>
    </div>
  );
}

/* ── Tab: Timeline ────────────────────────────────────────────────────────── */

function TimelineTab({ timeline }: { timeline: SymptomLog[] }) {
  const [openKey, setOpenKey] = useState<string | null>(null);
  const sorted = [...timeline].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  return (
    <div className="max-w-2xl">
      {sorted.length === 0 ? (
        <p className="text-sm text-ink-muted py-8 text-center">No check-ins logged yet.</p>
      ) : (
        <div className="relative">
          <div className="absolute left-[11px] top-2 bottom-2 w-px bg-sand-200" />
          <div className="space-y-3">
            {sorted.map((e, i) => {
              const flagged    = (e.bp_systolic ?? 0) >= 140;
              const rawText    = e.raw_text?.trim() || null;
              const bp         = e.bp_systolic != null ? `${e.bp_systolic}/${e.bp_diastolic}` : null;
              const summary    = rawText ?? (bp ? `BP ${bp}` : "Check-in");
              const isOpen     = openKey === e.timestamp + i;

              const chips = [
                e.headache_severity && e.headache_severity > 0 ? `Headache ${e.headache_severity}/10` : null,
                e.swelling_location && e.swelling_location !== "none" ? `Swelling: ${e.swelling_location}` : null,
                e.vision_changes === true ? "Vision changes" : null,
                e.fetal_movement ? `Movement: ${e.fetal_movement}` : null,
                e.medication_taken === false ? "Aspirin missed" : null,
              ].filter(Boolean) as string[];

              return (
                <div key={i} className="relative pl-9">
                  <div className={`absolute left-0 top-3 w-[22px] h-[22px] rounded-full flex items-center justify-center shadow-sm ${
                    flagged ? "bg-bloom-600 ring-2 ring-bloom-500/25" : "bg-bloom-500"
                  }`}>
                    {flagged
                      ? <span className="w-1.5 h-1.5 rounded-full bg-white" />
                      : <Check className="w-3 h-3 text-white" strokeWidth={3} />}
                  </div>

                  <button
                    onClick={() => setOpenKey(isOpen ? null : e.timestamp + i)}
                    className="w-full text-left bg-surface border border-sand-200 rounded-2xl p-4 hover:border-bloom-500/30 transition-colors">
                    <div className="flex items-baseline justify-between gap-3 mb-1">
                      <span className="font-semibold text-[13px] text-leaf-800">
                        {fmtDay(e.timestamp)}
                        <span className="text-ink-muted font-normal">
                          {" · "}{new Date(e.timestamp).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
                        </span>
                      </span>
                      <span className="flex items-center gap-1.5 shrink-0">
                        {bp && <span className="font-display text-[14px] text-ink">{bp}</span>}
                        <ChevronDown className={`w-4 h-4 text-ink-muted/40 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                      </span>
                    </div>
                    <p className="text-[12px] text-ink-muted leading-snug">{summary}</p>

                    {chips.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {chips.map((c) => (
                          <span key={c} className="text-[10px] px-1.5 py-0.5 rounded-full bg-sand-100 text-ink-muted border border-sand-200 font-medium">
                            {c}
                          </span>
                        ))}
                      </div>
                    )}

                    {isOpen && (
                      <div className="mt-3 pt-3 border-t border-sand-100" onClick={(ev) => ev.stopPropagation()}>
                        <p className="text-[11px] font-semibold text-ink/40 uppercase tracking-wider mb-2">What was logged</p>
                        {[
                          bp ? { Icon: HeartPulse, label: "Blood pressure", value: bp } : null,
                          e.headache_severity ? { Icon: AlertTriangle, label: "Headache", value: `${e.headache_severity}/10` } : null,
                          e.vision_changes ? { Icon: Eye, label: "Vision changes", value: "Reported" } : null,
                          e.swelling_location ? { Icon: Droplets, label: "Swelling", value: e.swelling_location } : null,
                          e.fetal_movement ? { Icon: Baby, label: "Baby's movement", value: e.fetal_movement } : null,
                          e.medication_taken != null ? { Icon: Pill, label: "Low-dose aspirin", value: e.medication_taken ? "Taken" : "Not taken" } : null,
                        ].filter(Boolean).map((r) => {
                          if (!r) return null;
                          const Icon = r.Icon;
                          return (
                            <div key={r.label} className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-sand-100/70 mb-1.5">
                              <div className="w-7 h-7 rounded-full bg-bloom-500/12 text-bloom-600 flex items-center justify-center shrink-0">
                                <Icon className="w-3.5 h-3.5" />
                              </div>
                              <span className="flex-1 text-[12px] text-leaf-800">{r.label}</span>
                              <span className="text-[12px] font-semibold text-leaf-800">{r.value}</span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
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
  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
      <div className="bg-surface border-b border-border px-6 py-4 shrink-0 shadow-sm shadow-black/[0.04]">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="font-display text-lg font-semibold text-ink">Escalations</h1>
            <p className="text-[12px] text-ink-muted mt-0.5">Structured summaries · evaluated by LLM-as-judge · traced in Arize</p>
          </div>
          {unread > 0 && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-risk-escalate-bg text-risk-escalate text-[11px] font-semibold border border-risk-escalate/20">
              <span className="w-1.5 h-1.5 rounded-full bg-risk-escalate animate-pulse" />{unread} unread
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="max-w-3xl mx-auto px-5 py-5">
          {items.length === 0 ? (
            <div className="py-16 text-center">
              <CheckCircle2 className="w-10 h-10 text-risk-ok mx-auto mb-3 opacity-50" />
              <p className="text-sm text-ink-muted">No escalations yet.</p>
            </div>
          ) : (
            <ul className="space-y-3">
              {items.map((e) => {
                const sev: DisplayRisk = e.severity === "escalate_urgent" ? "escalate" : e.severity as DisplayRisk;
                return (
                  <li key={e.escalation_id}
                    className={`bg-surface rounded-2xl border ${!e.acknowledged ? "border-risk-escalate/30 shadow-md shadow-risk-escalate/10" : "border-sand-200"}`}>
                    <div className="p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-center gap-3 min-w-0">
                          <FaceAvatar patientId={e.patient_id} size={38} />
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-display text-[15px] font-semibold text-ink">{e.patient_name}</span>
                              <RiskBadge risk={!e.acknowledged ? "escalate" : sev} />
                            </div>
                            <p className="text-[11px] text-ink-muted mt-0.5">{fmtTime(e.timestamp)}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {!e.acknowledged && (
                            <GhostBtn onClick={() => onAck(e.escalation_id)}>
                              <X className="w-3.5 h-3.5 mr-1" />Acknowledge
                            </GhostBtn>
                          )}
                          <PrimaryBtn onClick={() => onOpenPatient(e.patient_id)}>
                            Open patient<ChevronRight className="w-3.5 h-3.5 ml-1" />
                          </PrimaryBtn>
                        </div>
                      </div>

                      <p className="mt-3.5 text-[13px] text-ink leading-relaxed font-display">{e.summary}</p>

                      {e.triggering_readings.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {e.triggering_readings.map((v) => (
                            <span key={v} className="px-2 py-1 text-[11px] rounded-full bg-sand-100 text-leaf-800 font-mono border border-sand-200">{v}</span>
                          ))}
                        </div>
                      )}

                      <div className="mt-3 pt-3 border-t border-sand-100">
                        <p className="text-[10px] font-semibold uppercase tracking-widest text-ink-muted/70 mb-1">Recommended action</p>
                        <p className="text-[13px] text-leaf-800">{e.recommended_action}</p>
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

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-widest text-bloom-600">{children}</p>
  );
}

function StatCard({ label, value, sub, alert = false }: {
  label: string; value: string; sub: string; alert?: boolean;
}) {
  return (
    <div className="bg-surface border border-sand-200 rounded-2xl p-4">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-bloom-600 mb-2">{label}</p>
      <p className={`font-display text-[28px] font-semibold tabular-nums leading-none ${alert ? "text-risk-escalate" : "text-ink"}`}>{value}</p>
      <p className="text-[11px] text-ink-muted mt-1">{sub}</p>
    </div>
  );
}

function AdherenceCard({ pct }: { pct: number | null }) {
  const SIZE = 70; const R = 27; const SW = 5.5;
  const circ = 2 * Math.PI * R;
  const fill = pct != null ? Math.max(0, Math.min(1, pct / 100)) * circ : 0;
  const fillColor = pct == null ? "#E6DEF3"
    : pct >= 80 ? "#2D6A4F" : pct >= 60 ? "#92400E" : "#9B1C1C";
  return (
    <div className="bg-surface border border-sand-200 rounded-2xl p-4 flex flex-col">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-bloom-600 mb-2">Adherence</p>
      <div className="flex items-center gap-3">
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="shrink-0">
          <circle cx={SIZE/2} cy={SIZE/2} r={R} fill="none" stroke="#E6DEF3" strokeWidth={SW} />
          <circle cx={SIZE/2} cy={SIZE/2} r={R} fill="none" stroke={fillColor} strokeWidth={SW}
            strokeDasharray={`${fill} ${circ - fill}`} strokeLinecap="round"
            transform={`rotate(-90 ${SIZE/2} ${SIZE/2})`}
            style={{ transition: "stroke-dasharray 0.5s ease" }} />
          <text x={SIZE/2} y={SIZE/2-4} textAnchor="middle" dominantBaseline="central"
            fontSize="14" fontWeight="700" fill="#2A2435">{pct != null ? `${pct}%` : "—"}</text>
          <text x={SIZE/2} y={SIZE/2+11} textAnchor="middle" dominantBaseline="central"
            fontSize="7.5" fontWeight="600" fill="#6B6478">ASPIRIN</text>
        </svg>
        <p className="text-[11px] text-ink-muted leading-relaxed">
          {pct == null ? "No medication data recorded." :
           pct >= 80  ? "Good adherence this period." :
           pct >= 60  ? "Some doses missed — worth discussing." :
                        "Low adherence — may affect outcomes."}
        </p>
      </div>
    </div>
  );
}

function RiskDial({ score }: { score: number }) {
  const SIZE = 64; const R = 26; const SW = 5;
  const circ = 2 * Math.PI * R;
  const fill = score * circ;
  const fillColor = score > 0.65 ? "#FCA5A5" : score > 0.4 ? "#FCD34D" : "#6EE7B7";
  return (
    <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="shrink-0 opacity-80">
      <circle cx={SIZE/2} cy={SIZE/2} r={R} fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth={SW} />
      <circle cx={SIZE/2} cy={SIZE/2} r={R} fill="none" stroke={fillColor} strokeWidth={SW}
        strokeDasharray={`${fill} ${circ - fill}`} strokeLinecap="round"
        transform={`rotate(-90 ${SIZE/2} ${SIZE/2})`} />
    </svg>
  );
}

function BPChart({ data }: { data: { day: string; sys: number; dia: number }[] }) {
  const W = 480; const H = 130;
  const PAD = { l: 28, r: 8, t: 8, b: 20 };
  const xs = (i: number) => PAD.l + (i * (W - PAD.l - PAD.r)) / Math.max(1, data.length - 1);
  const ys = (v: number) => PAD.t + (H - PAD.t - PAD.b) * (1 - (v - 60) / 100);
  const sysPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${xs(i)},${ys(d.sys)}`).join(" ");
  const diaPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${xs(i)},${ys(d.dia)}`).join(" ");

  return (
    <div className="mt-3 w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="none">
        {[80, 100, 120, 140].map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W-PAD.r} y1={ys(v)} y2={ys(v)} stroke="#E6DEF3" strokeWidth="1" />
            <text x={4} y={ys(v)+3} fontSize="9" fill="#6B6478">{v}</text>
          </g>
        ))}
        <line x1={PAD.l} x2={W-PAD.r} y1={ys(140)} y2={ys(140)} stroke="#9B1C1C" strokeWidth="1" strokeDasharray="4 3" opacity="0.5" />
        <path d={sysPath} stroke="#9D6FE0" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <path d={diaPath} stroke="#C7A4EC" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        {data.map((d, i) => (
          <g key={i}>
            <circle cx={xs(i)} cy={ys(d.sys)} r={d.sys >= 140 ? 4.5 : 3} fill={d.sys >= 140 ? "#9B1C1C" : "#9D6FE0"} />
            <circle cx={xs(i)} cy={ys(d.dia)} r="2.5" fill="#C7A4EC" />
            <text x={xs(i)} y={H-4} fontSize="9" fill="#6B6478" textAnchor="middle">{d.day}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function BPTrendChip({ trend }: { trend: "up" | "down" | "stable" }) {
  const map = {
    up:     { label: "Trending up",   color: "text-risk-escalate", Icon: TrendingUp },
    down:   { label: "Trending down", color: "text-risk-ok",       Icon: TrendingUp },
    stable: { label: "Stable",        color: "text-ink-muted",     Icon: Activity },
  };
  const t = map[trend];
  return (
    <span className={`flex items-center gap-1 text-[11px] font-semibold ${t.color}`}>
      <t.Icon className={`w-3 h-3 ${trend === "down" ? "rotate-180" : ""}`} />
      {t.label}
    </span>
  );
}

function PrimaryBtn({ children, onClick, disabled }: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="inline-flex items-center h-8 px-3.5 rounded-lg bg-bloom-500 hover:bg-bloom-600 text-white text-[13px] font-semibold shadow-sm shadow-bloom-500/25 transition-all duration-100 active:scale-95 disabled:opacity-50 disabled:pointer-events-none">
      {children}
    </button>
  );
}

function GhostBtn({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button onClick={onClick}
      className="inline-flex items-center h-8 px-3 rounded-lg text-[13px] font-medium text-ink-muted border border-sand-200 bg-surface hover:bg-sand-100 hover:text-ink transition-all duration-100 active:scale-95">
      {children}
    </button>
  );
}

function IconBtn({ icon: Icon, label, onClick }: {
  icon: React.FC<{className?: string}>; label: string; onClick: () => void;
}) {
  return (
    <button onClick={onClick} title={label}
      className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg text-[13px] font-medium text-ink-muted border border-sand-200 bg-surface hover:bg-sand-100 hover:text-ink transition-all duration-100 active:scale-95">
      <Icon className="w-3.5 h-3.5" />
      {label}
    </button>
  );
}
