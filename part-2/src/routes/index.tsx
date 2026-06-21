import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  patients,
  escalations as seedEscalations,
  type Patient,
  type Risk,
  type Escalation,
} from "@/lib/clinician-data";

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

type View = "panel" | "escalations";

function ClinicianDashboard() {
  const [view, setView] = useState<View>("panel");
  const [selectedId, setSelectedId] = useState<string>(patients[0].id);
  const [escalations, setEscalations] = useState<Escalation[]>(seedEscalations);

  const sorted = useMemo(
    () => [...patients].sort((a, b) => b.riskScore - a.riskScore),
    [],
  );
  const selected = patients.find((p) => p.id === selectedId) ?? patients[0];
  const newEscalations = escalations.filter((e) => e.status === "new").length;

  return (
    <div className="min-h-screen bg-background">
      <TopBar
        view={view}
        onView={setView}
        newEscalations={newEscalations}
      />
      {view === "panel" ? (
        <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-0 border-t border-border">
          <aside className="border-r border-border bg-surface min-h-[calc(100vh-64px)]">
            <PanelHeader count={sorted.length} />
            <ul className="divide-y divide-border">
              {sorted.map((p) => (
                <PatientRow
                  key={p.id}
                  patient={p}
                  active={p.id === selected.id}
                  onSelect={() => setSelectedId(p.id)}
                />
              ))}
            </ul>
          </aside>
          <main className="bg-background">
            <PatientDetail patient={selected} />
          </main>
        </div>
      ) : (
        <EscalationsInbox
          items={escalations}
          onAck={(id) =>
            setEscalations((es) =>
              es.map((e) => (e.id === id ? { ...e, status: "acknowledged" } : e)),
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

/* ------------------------------ Top Bar ------------------------------ */

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
    <header className="h-16 px-6 flex items-center justify-between bg-surface">
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-2">
          <CadenceMark />
          <div className="leading-tight">
            <div className="font-display text-lg font-semibold tracking-tight">Cadence</div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
              Clinician
            </div>
          </div>
        </div>
        <nav className="flex items-center gap-1 text-sm">
          <NavBtn active={view === "panel"} onClick={() => onView("panel")}>
            Patient panel
          </NavBtn>
          <NavBtn active={view === "escalations"} onClick={() => onView("escalations")}>
            <span className="flex items-center gap-2">
              Escalations
              {newEscalations > 0 && (
                <span className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 text-[11px] font-semibold rounded-full bg-risk-escalate text-white">
                  {newEscalations}
                </span>
              )}
            </span>
          </NavBtn>
        </nav>
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right leading-tight">
          <div className="text-sm font-medium">Dr. Aiyana Reyes, MD</div>
          <div className="text-[11px] text-muted-foreground">MFM · Westside Women's Health</div>
        </div>
        <div className="w-9 h-9 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-semibold">
          AR
        </div>
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
      className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
        active
          ? "bg-secondary text-secondary-foreground"
          : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function CadenceMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden>
      <circle cx="14" cy="14" r="13" stroke="currentColor" strokeOpacity="0.15" />
      <path
        d="M4 16 L9 16 L11 11 L14 20 L17 8 L20 16 L24 16"
        stroke="oklch(0.38 0.06 200)"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

/* ------------------------------ Panel ------------------------------ */

function PanelHeader({ count }: { count: number }) {
  const esc = patients.filter((p) => p.risk === "escalate").length;
  const mon = patients.filter((p) => p.risk === "monitor").length;
  return (
    <div className="px-5 py-4 border-b border-border">
      <div className="flex items-baseline justify-between">
        <h2 className="font-display text-base font-semibold">My patients</h2>
        <span className="text-xs text-muted-foreground">{count} active</span>
      </div>
      <div className="mt-2 text-xs text-muted-foreground">
        <span className="text-risk-escalate font-semibold">{esc} escalate</span>
        <span className="mx-2 text-border-strong">·</span>
        <span className="text-risk-monitor font-semibold">{mon} monitor</span>
        <span className="mx-2 text-border-strong">·</span>
        <span>{count - esc - mon} on track</span>
      </div>
    </div>
  );
}

function PatientRow({
  patient,
  active,
  onSelect,
}: {
  patient: Patient;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        onClick={onSelect}
        className={`w-full text-left px-5 py-4 transition-colors ${
          active ? "bg-accent/40" : "hover:bg-muted"
        }`}
      >
        <div className="flex items-start gap-3">
          <RiskDot risk={patient.risk} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-sm truncate">{patient.name}</span>
              <RiskBadge risk={patient.risk} small />
            </div>
            <div className="text-xs text-muted-foreground mt-0.5 truncate">
              {patient.gestation} · {patient.condition}
            </div>
            <div className="text-[11px] text-muted-foreground mt-1.5 flex items-center gap-2">
              <span>Last check-in {patient.lastCheckin}</span>
            </div>
          </div>
        </div>
      </button>
    </li>
  );
}

function RiskDot({ risk }: { risk: Risk }) {
  const cls =
    risk === "escalate"
      ? "bg-risk-escalate"
      : risk === "monitor"
        ? "bg-risk-monitor"
        : "bg-risk-ok";
  return <span className={`mt-1.5 inline-block w-2 h-2 rounded-full ${cls}`} />;
}

function RiskBadge({ risk, small = false }: { risk: Risk; small?: boolean }) {
  const map: Record<Risk, { label: string; bg: string; fg: string }> = {
    ok: { label: "On track", bg: "bg-risk-ok-bg", fg: "text-risk-ok" },
    monitor: { label: "Monitor", bg: "bg-risk-monitor-bg", fg: "text-risk-monitor" },
    escalate: { label: "Escalate", bg: "bg-risk-escalate-bg", fg: "text-risk-escalate" },
  };
  const c = map[risk];
  return (
    <span
      className={`inline-flex items-center gap-1.5 ${c.bg} ${c.fg} font-semibold uppercase tracking-wider rounded-md ${
        small ? "text-[10px] px-1.5 py-0.5" : "text-[11px] px-2 py-1"
      }`}
    >
      {risk === "escalate" && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />}
      {c.label}
    </span>
  );
}

/* ------------------------------ Detail ------------------------------ */

function PatientDetail({ patient }: { patient: Patient }) {
  const hasDetail = patient.timeline.length > 0;
  return (
    <div className="max-w-[1100px] mx-auto px-8 py-8">
      <div className="flex items-start justify-between gap-6 flex-wrap">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-display text-3xl font-semibold tracking-tight">
              {patient.name}
            </h1>
            <RiskBadge risk={patient.risk} />
          </div>
          <div className="mt-2 text-sm text-muted-foreground">
            {patient.age} y/o · {patient.gestation} · {patient.condition}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            Next visit: <span className="text-foreground font-medium">{patient.nextVisit}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ActionBtn>Message patient</ActionBtn>
          <ActionBtn>Book sooner</ActionBtn>
          <ActionBtn>Flag for nurse</ActionBtn>
          <ActionBtn primary>Add note</ActionBtn>
        </div>
      </div>

      {!hasDetail ? (
        <div className="mt-10 rounded-xl border border-dashed border-border-strong bg-surface px-6 py-12 text-center text-sm text-muted-foreground">
          Full briefing for {patient.name} will appear here. Select{" "}
          <span className="font-medium text-foreground">Maria Chen</span> to see a complete
          example.
        </div>
      ) : (
        <>
          {/* Risk + briefing */}
          <section className="mt-8 grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-5">
            <Card className="p-6">
              <SectionLabel>Pre-visit briefing</SectionLabel>
              <p className="mt-3 text-[15px] leading-relaxed text-foreground">
                {patient.briefing}
              </p>
              <div className="mt-5 flex items-center gap-4 text-xs text-muted-foreground">
                <Stat label="Check-ins" value="9 / 9" />
                <Divider />
                <Stat label="Adherence" value={`${Math.round(patient.adherence * 100)}%`} />
                <Divider />
                <Stat label="Days since visit" value="9" />
                <Divider />
                <Stat label="Days to next" value="5" />
              </div>
            </Card>
            <Card className="p-6">
              <SectionLabel>Risk assessment</SectionLabel>
              <div className="mt-3 flex items-end gap-3">
                <div className="font-display text-4xl font-semibold text-risk-escalate">
                  {Math.round(patient.riskScore * 100)}
                </div>
                <div className="pb-1 text-xs text-muted-foreground">/ 100</div>
              </div>
              <RiskMeter score={patient.riskScore} />
              <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                {patient.riskRationale}
              </p>
            </Card>
          </section>

          {/* Patterns + BP chart */}
          <section className="mt-5 grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-5">
            <Card className="p-6">
              <SectionLabel>Pattern detection</SectionLabel>
              <ul className="mt-4 space-y-3">
                {patient.patterns.map((p) => (
                  <li
                    key={p.title}
                    className="flex items-start gap-3 p-3 rounded-lg bg-surface-elevated border border-border"
                  >
                    <RiskDot risk={p.severity} />
                    <div className="flex-1">
                      <div className="text-sm font-medium">{p.title}</div>
                      <div className="text-xs text-muted-foreground mt-1 leading-relaxed">
                        {p.detail}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
            <Card className="p-6">
              <SectionLabel>Blood pressure · 9 days</SectionLabel>
              <BPChart data={patient.bpTrend} />
              <div className="mt-3 flex items-center gap-4 text-[11px] text-muted-foreground">
                <Legend color="bg-primary" label="Systolic" />
                <Legend color="bg-accent-foreground" label="Diastolic" />
                <Legend color="bg-risk-escalate" label="140/90 threshold" dashed />
              </div>
            </Card>
          </section>

          {/* Starters + timeline */}
          <section className="mt-5 grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5">
            <Card className="p-6">
              <SectionLabel>Conversation starters</SectionLabel>
              <ol className="mt-4 space-y-3">
                {patient.starters.map((s, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="shrink-0 w-6 h-6 rounded-full bg-secondary text-secondary-foreground text-[11px] font-semibold flex items-center justify-center">
                      {i + 1}
                    </span>
                    <span className="text-sm leading-relaxed">{s}</span>
                  </li>
                ))}
              </ol>
              <div className="mt-5 pt-4 border-t border-border text-[11px] text-muted-foreground">
                Generated by Cadence · grounded in patient's care plan · independently evaluated
              </div>
            </Card>
            <Card className="p-6">
              <SectionLabel>Timeline · since last visit</SectionLabel>
              <ol className="mt-4 relative">
                <span className="absolute left-[7px] top-1 bottom-1 w-px bg-border" />
                {patient.timeline.map((e, i) => (
                  <li key={i} className="relative pl-7 pb-5 last:pb-0">
                    <span
                      className={`absolute left-0 top-1.5 w-[15px] h-[15px] rounded-full border-2 border-background ${
                        e.flag ? "bg-risk-escalate" : "bg-border-strong"
                      }`}
                    />
                    <div className="flex items-baseline justify-between gap-3">
                      <div className="text-sm font-medium">{e.summary}</div>
                      <div className="text-[11px] text-muted-foreground shrink-0">{e.date}</div>
                    </div>
                    {e.detail && (
                      <div className="mt-1 text-xs text-muted-foreground leading-relaxed">
                        {e.detail}
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            </Card>
          </section>

          <div className="mt-6 text-[11px] text-muted-foreground text-center">
            All entries traced in Arize · LLM-as-judge confidence on most recent escalation: 0.97
          </div>
        </>
      )}
    </div>
  );
}

function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`bg-surface border border-border rounded-xl ${className}`}>{children}</div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider">{label}</div>
      <div className="text-sm font-semibold text-foreground mt-0.5">{value}</div>
    </div>
  );
}

function Divider() {
  return <span className="w-px h-8 bg-border" />;
}

function ActionBtn({
  children,
  primary,
}: {
  children: React.ReactNode;
  primary?: boolean;
}) {
  return (
    <button
      className={`px-3 py-1.5 text-sm rounded-md font-medium transition-colors ${
        primary
          ? "bg-primary text-primary-foreground hover:opacity-90"
          : "bg-surface border border-border hover:bg-muted text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function RiskMeter({ score }: { score: number }) {
  return (
    <div className="mt-3 h-2 rounded-full bg-muted overflow-hidden relative">
      <div
        className="h-full bg-gradient-to-r from-risk-ok via-risk-monitor to-risk-escalate"
        style={{ width: `${score * 100}%` }}
      />
      <span
        className="absolute top-0 bottom-0 w-px bg-foreground/30"
        style={{ left: "70%" }}
        aria-label="escalation threshold"
      />
    </div>
  );
}

function Legend({
  color,
  label,
  dashed,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {dashed ? (
        <span className="w-3 h-px border-t border-dashed border-risk-escalate" />
      ) : (
        <span className={`w-2.5 h-2.5 rounded-sm ${color}`} />
      )}
      {label}
    </span>
  );
}

function BPChart({ data }: { data: { day: string; sys: number; dia: number }[] }) {
  if (!data.length) return null;
  const W = 520;
  const H = 180;
  const PAD = { l: 28, r: 8, t: 12, b: 22 };
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
    <div className="mt-3 w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="none">
        {[80, 100, 120, 140].map((v) => (
          <g key={v}>
            <line
              x1={PAD.l}
              x2={W - PAD.r}
              y1={ys(v)}
              y2={ys(v)}
              stroke="oklch(0.91 0.008 230)"
              strokeWidth="1"
            />
            <text x={4} y={ys(v) + 3} fontSize="9" fill="oklch(0.48 0.02 240)">
              {v}
            </text>
          </g>
        ))}
        <line
          x1={PAD.l}
          x2={W - PAD.r}
          y1={threshold}
          y2={threshold}
          stroke="oklch(0.5 0.2 25)"
          strokeWidth="1"
          strokeDasharray="4 4"
          opacity="0.6"
        />
        <path d={sysPath} stroke="oklch(0.38 0.06 200)" strokeWidth="2" fill="none" />
        <path d={diaPath} stroke="oklch(0.28 0.05 200)" strokeWidth="2" fill="none" opacity="0.6" />
        {data.map((d, i) => (
          <g key={i}>
            <circle
              cx={xs(i)}
              cy={ys(d.sys)}
              r={d.sys >= 140 ? 4 : 2.5}
              fill={d.sys >= 140 ? "oklch(0.5 0.2 25)" : "oklch(0.38 0.06 200)"}
            />
            <circle cx={xs(i)} cy={ys(d.dia)} r="2.5" fill="oklch(0.28 0.05 200)" opacity="0.7" />
            <text
              x={xs(i)}
              y={H - 6}
              fontSize="9"
              fill="oklch(0.48 0.02 240)"
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

/* ------------------------------ Escalations ------------------------------ */

function EscalationsInbox({
  items,
  onAck,
  onOpenPatient,
}: {
  items: Escalation[];
  onAck: (id: string) => void;
  onOpenPatient: (pid: string) => void;
}) {
  return (
    <div className="max-w-[900px] mx-auto px-8 py-8">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">Escalations</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Structured clinical summaries. Real-time. Independently evaluated before they reach
            you.
          </p>
        </div>
        <div className="text-xs text-muted-foreground">
          {items.filter((e) => e.status === "new").length} new ·{" "}
          {items.filter((e) => e.status === "acknowledged").length} acknowledged
        </div>
      </div>
      <ul className="mt-6 space-y-4">
        {items.map((e) => (
          <li
            key={e.id}
            className={`rounded-xl border bg-surface ${
              e.status === "new" ? "border-risk-escalate/40" : "border-border"
            }`}
          >
            <div className="p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <RiskBadge risk={e.status === "new" ? "escalate" : "monitor"} small />
                    <span className="text-[11px] text-muted-foreground">
                      {e.receivedAt} · routed via Poke
                    </span>
                  </div>
                  <h3 className="mt-2 font-display text-xl font-semibold">{e.patientName}</h3>
                  <div className="text-sm text-muted-foreground mt-0.5">{e.headline}</div>
                </div>
                <div className="flex items-center gap-2">
                  {e.status === "new" && (
                    <button
                      onClick={() => onAck(e.id)}
                      className="px-3 py-1.5 text-sm rounded-md bg-surface border border-border hover:bg-muted font-medium"
                    >
                      Acknowledge
                    </button>
                  )}
                  <button
                    onClick={() => onOpenPatient(e.patientId)}
                    className="px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground font-medium hover:opacity-90"
                  >
                    Open patient
                  </button>
                </div>
              </div>

              <p className="mt-4 text-sm leading-relaxed">{e.summary}</p>

              <div className="mt-4 flex flex-wrap gap-2">
                {e.vitals.map((v) => (
                  <span
                    key={v}
                    className="px-2.5 py-1 text-xs rounded-md bg-secondary text-secondary-foreground font-mono"
                  >
                    {v}
                  </span>
                ))}
              </div>

              <div className="mt-4 pt-4 border-t border-border text-sm">
                <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground font-semibold">
                  Recommended action ·{" "}
                </span>
                <span className="text-foreground">{e.recommended}</span>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
