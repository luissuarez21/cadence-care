import { useState, type ReactNode } from "react";
import { Check, HeartPulse, Baby, Pill, AlertTriangle } from "lucide-react";

export type Checkin = {
  bpMorning?: string;
  bpEvening?: string;
  symptoms?: string[];
  symptomsDone?: boolean;
  movement?: "normal" | "less";
  aspirin?: boolean;
};

// ACOG PB 222 preeclampsia warning signs (clinically validated set).
const SYMPTOMS = ["Headache", "Vision changes", "Swelling", "Upper belly pain", "Short of breath"];

export function DailyCheckin({
  checkin,
  busy,
  onLog,
}: {
  checkin: Checkin;
  busy: boolean;
  onLog: (message: string, patch: Checkin) => void;
}) {
  const done = [
    checkin.bpMorning,
    checkin.bpEvening,
    checkin.symptomsDone,
    checkin.movement,
    checkin.aspirin,
  ].filter(Boolean).length;
  const total = 5;
  const allDone = done === total;

  return (
    <section className="bg-white rounded-3xl border border-sand-200 shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-[15px] font-semibold text-leaf-800 leading-tight">Today's check-in</h3>
          <p className="text-[12px] text-ink-muted mt-0.5">
            {allDone ? "All done — nice work." : "Day 9 · log these for Dr. Reyes"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-semibold text-bloom-600 tabular-nums">
            {done}/{total}
          </span>
          <div className="h-1.5 w-14 rounded-full bg-sand-200 overflow-hidden">
            <div
              className="h-full bg-bloom-500 transition-all duration-300"
              style={{ width: `${(done / total) * 100}%` }}
            />
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <BpRow
          label="Morning blood pressure"
          value={checkin.bpMorning}
          busy={busy}
          onLog={(v) => onLog(`My morning blood pressure was ${v}.`, { bpMorning: v })}
        />
        <BpRow
          label="Evening blood pressure"
          value={checkin.bpEvening}
          busy={busy}
          onLog={(v) => onLog(`My evening blood pressure was ${v}.`, { bpEvening: v })}
        />
        <SymptomRow
          done={checkin.symptomsDone}
          selected={checkin.symptoms}
          busy={busy}
          onLog={(list) =>
            onLog(
              list.length === 0
                ? "No warning symptoms today — no headache, vision changes, swelling, upper belly pain, or shortness of breath."
                : `Today I'm noticing: ${list.join(", ").toLowerCase()}.`,
              { symptoms: list, symptomsDone: true },
            )
          }
        />
        <ChoiceRow
          label="Baby's movement"
          icon={<Baby className="size-4" />}
          value={
            checkin.movement ? (checkin.movement === "normal" ? "Normal" : "Less than usual") : undefined
          }
          options={[
            { key: "normal", label: "Normal" },
            { key: "less", label: "Less" },
          ]}
          busy={busy}
          onPick={(key) =>
            onLog(
              key === "normal"
                ? "Baby has been moving normally today."
                : "Baby is moving less than usual today.",
              { movement: key as "normal" | "less" },
            )
          }
        />
        <ToggleRow
          label="Low-dose aspirin"
          icon={<Pill className="size-4" />}
          done={checkin.aspirin}
          actionLabel="Mark taken"
          doneLabel="Taken"
          busy={busy}
          onDone={() => onLog("I took my low-dose aspirin today.", { aspirin: true })}
        />
      </div>
    </section>
  );
}

function TaskIcon({ children, done }: { children: ReactNode; done?: boolean }) {
  return (
    <div
      className={
        "size-8 rounded-full grid place-items-center shrink-0 " +
        (done ? "bg-bloom-500/15 text-bloom-600" : "bg-sand-200/70 text-leaf-700")
      }
    >
      {children}
    </div>
  );
}

function DoneRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-2xl bg-bloom-500/[0.06]">
      <TaskIcon done>{icon}</TaskIcon>
      <span className="flex-1 text-[13.5px] font-medium text-ink-muted min-w-0 truncate">{label}</span>
      <span className="text-[13px] font-semibold text-leaf-800">{value}</span>
      <Check className="size-4 text-bloom-600 shrink-0" strokeWidth={3} />
    </div>
  );
}

function BpRow({
  label,
  value,
  busy,
  onLog,
}: {
  label: string;
  value?: string;
  busy: boolean;
  onLog: (v: string) => void;
}) {
  const [v, setV] = useState("");
  if (value) return <DoneRow icon={<HeartPulse className="size-4" />} label={label} value={value} />;
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded-2xl bg-sand-100/70">
      <TaskIcon>
        <HeartPulse className="size-4" />
      </TaskIcon>
      <span className="flex-1 text-[13.5px] font-medium text-leaf-800 min-w-0 truncate">{label}</span>
      <input
        value={v}
        onChange={(e) => setV(e.target.value)}
        inputMode="text"
        placeholder="120/80"
        /* 16px min font-size prevents iOS Safari auto-zoom on focus */
        className="w-[80px] text-center bg-white border border-sand-200 rounded-lg px-2 py-1.5 text-[16px] outline-none focus:border-bloom-500/50"
        onKeyDown={(e) => {
          if (e.key === "Enter" && v.trim() && !busy) {
            onLog(v.trim());
            setV("");
          }
        }}
      />
      <button
        type="button"
        disabled={!v.trim() || busy}
        onClick={() => {
          onLog(v.trim());
          setV("");
        }}
        className="text-[12px] font-semibold text-bloom-600 disabled:opacity-30 px-1"
      >
        Log
      </button>
    </div>
  );
}

function ChoiceRow({
  label,
  icon,
  value,
  options,
  busy,
  onPick,
}: {
  label: string;
  icon: ReactNode;
  value?: string;
  options: { key: string; label: string }[];
  busy: boolean;
  onPick: (key: string) => void;
}) {
  if (value) return <DoneRow icon={icon} label={label} value={value} />;
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded-2xl bg-sand-100/70">
      <TaskIcon>{icon}</TaskIcon>
      <span className="flex-1 text-[13.5px] font-medium text-leaf-800 min-w-0 truncate">{label}</span>
      <div className="flex gap-1.5">
        {options.map((o) => (
          <button
            key={o.key}
            type="button"
            disabled={busy}
            onClick={() => onPick(o.key)}
            className="text-[12px] font-medium px-2.5 py-1.5 rounded-full bg-white border border-sand-200 text-leaf-800 hover:border-bloom-500/40 disabled:opacity-40 transition-colors"
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ToggleRow({
  label,
  icon,
  done,
  actionLabel,
  doneLabel,
  busy,
  onDone,
}: {
  label: string;
  icon: ReactNode;
  done?: boolean;
  actionLabel: string;
  doneLabel: string;
  busy: boolean;
  onDone: () => void;
}) {
  if (done) return <DoneRow icon={icon} label={label} value={doneLabel} />;
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded-2xl bg-sand-100/70">
      <TaskIcon>{icon}</TaskIcon>
      <span className="flex-1 text-[13.5px] font-medium text-leaf-800 min-w-0 truncate">{label}</span>
      <button
        type="button"
        disabled={busy}
        onClick={onDone}
        className="text-[12px] font-semibold px-3 py-1.5 rounded-full bg-bloom-500 text-white disabled:opacity-40 active:scale-95 transition-transform"
      >
        {actionLabel}
      </button>
    </div>
  );
}

function SymptomRow({
  done,
  selected,
  busy,
  onLog,
}: {
  done?: boolean;
  selected?: string[];
  busy: boolean;
  onLog: (list: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);

  if (done) {
    const summary = selected && selected.length > 0 ? selected.join(", ") : "None";
    return <DoneRow icon={<AlertTriangle className="size-4" />} label="Warning symptoms" value={summary} />;
  }

  const toggle = (s: string) =>
    setPicked((p) => (p.includes(s) ? p.filter((x) => x !== s) : [...p, s]));

  return (
    <div className="rounded-2xl bg-sand-100/70 px-3 py-2">
      <div className="flex items-center gap-3">
        <TaskIcon>
          <AlertTriangle className="size-4" />
        </TaskIcon>
        <span className="flex-1 text-[13.5px] font-medium text-leaf-800 min-w-0 truncate">
          Any warning symptoms?
        </span>
        {!open && (
          <div className="flex gap-1.5">
            <button
              type="button"
              disabled={busy}
              onClick={() => onLog([])}
              className="text-[12px] font-medium px-2.5 py-1.5 rounded-full bg-white border border-sand-200 text-leaf-800 hover:border-bloom-500/40 disabled:opacity-40 transition-colors"
            >
              None
            </button>
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="text-[12px] font-medium px-2.5 py-1.5 rounded-full bg-white border border-sand-200 text-leaf-800 hover:border-bloom-500/40 transition-colors"
            >
              Add
            </button>
          </div>
        )}
      </div>
      {open && (
        <div className="mt-2.5 pl-11">
          <div className="flex flex-wrap gap-1.5 mb-2.5">
            {SYMPTOMS.map((s) => {
              const on = picked.includes(s);
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() => toggle(s)}
                  className={
                    "text-[12px] font-medium px-2.5 py-1.5 rounded-full border transition-colors " +
                    (on
                      ? "bg-bloom-500 text-white border-bloom-500"
                      : "bg-white text-leaf-800 border-sand-200 hover:border-bloom-500/40")
                  }
                >
                  {s}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            disabled={busy || picked.length === 0}
            onClick={() => onLog(picked)}
            className="text-[12px] font-semibold text-bloom-600 disabled:opacity-30"
          >
            {picked.length ? `Log ${picked.length} symptom${picked.length > 1 ? "s" : ""}` : "Select symptoms"}
          </button>
        </div>
      )}
    </div>
  );
}
