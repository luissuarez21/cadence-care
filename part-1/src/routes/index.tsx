import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Send, Heart, ArrowRight, Check, HeartPulse, Baby, Pill, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { PatientShell } from "@/components/PatientShell";
import { api, PATIENT_ID } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Today — Cadence" },
      { name: "description", content: "Your daily check-in with Cadence." },
    ],
  }),
  component: TodayPage,
});

type Msg = {
  id: number;
  from: "cadence" | "maria";
  text: string;
  flagged?: boolean;
};

const GREETING: Msg = {
  id: 0,
  from: "cadence",
  text: "Good afternoon, Maria. How are you feeling today? Take your time — tell me whatever's on your mind.",
};

type CareMessage = { text: string; timestamp: string };

type Checkin = {
  bpMorning?: string;
  bpEvening?: string;
  movement?: "normal" | "less";
  aspirin?: boolean;
};

function TodayPage() {
  // A fresh session id per page load → conversation starts clean every reload.
  // The backend keys history off this; a new id means empty history → greeting only.
  const [sessionId] = useState(() =>
    typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `s-${Date.now()}`,
  );
  const [messages, setMessages] = useState<Msg[]>([GREETING]);
  const [careMessages, setCareMessages] = useState<CareMessage[]>([]);
  const [checkin, setCheckin] = useState<Checkin>({});
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Rehydrate thread from history on mount
  useEffect(() => {
    api
      .get<{ patient_id: string; session_id: string; messages: Array<{ sender: string; text: string; timestamp: string; flagged?: boolean }> }>(`/chat/history?session_id=${sessionId}`)
      .then((res) => {
        if (res.messages.length > 0) {
          setMessages(
            res.messages.map((m, i) => ({
              id: i,
              from: m.sender === "cadence" ? "cadence" : "maria",
              text: m.text,
              flagged: m.flagged ?? false,
            })),
          );
        }
      })
      .catch(() => {
        // Network error — keep the default greeting, don't alert
      });

    // Messages the care team sent to the patient (CAD-35)
    api
      .get<{ patient_id: string; messages: Array<{ text: string; timestamp: string }> }>("/patient/messages")
      .then((res) => setCareMessages(res.messages))
      .catch(() => {
        // Non-fatal — banner just won't show
      });

    inputRef.current?.focus();
  }, [sessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing]);

  const flagged = messages.some((m) => m.flagged);

  /**
   * Send a message to the agent. In `silent` mode (used by the daily check-in
   * panel) the patient's text is logged without a chat bubble, and Cade only
   * speaks back in the thread if the reading trips a red flag. Routine logging
   * stays quiet; escalation is conversational.
   */
  async function sendToAgent(
    text: string,
    opts: { silent?: boolean } = {},
  ): Promise<{ reply: string; flagged: boolean } | null> {
    if (!opts.silent) {
      setMessages((m) => [...m, { id: Date.now(), from: "maria", text }]);
    }
    setSending(true);
    setTyping(true);
    try {
      const res = await api.post<{ reply: string; flagged: boolean; risk?: unknown }>("/chat/message", {
        patient_id: PATIENT_ID,
        message: text,
        session_id: sessionId,
      });
      setTyping(false);
      if (!opts.silent || res.flagged) {
        setMessages((m) => [
          ...m,
          { id: Date.now() + 1, from: "cadence", text: res.reply, flagged: res.flagged },
        ]);
      }
      return res;
    } catch {
      setTyping(false);
      toast.error("Couldn't reach Cadence — please try again.");
      return null;
    } finally {
      setSending(false);
    }
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    const res = await sendToAgent(text);
    if (!res) setInput(text); // restore on failure
  }

  // One check-in task logs through the agent (quiet unless it red-flags),
  // then records the value in the panel.
  async function logTask(message: string, patch: Checkin) {
    if (sending) return;
    const res = await sendToAgent(message, { silent: true });
    if (res) setCheckin((c) => ({ ...c, ...patch }));
  }

  return (
    <PatientShell>
      {/* Daily check-in — structured logging, separate from the chat */}
      <DailyCheckin checkin={checkin} busy={sending} onLog={logTask} />

      {/* Messages from the care team (CAD-35) */}
      {careMessages.length > 0 && (
        <div className="mb-6 space-y-2">
          {careMessages.map((m, i) => (
            <div
              key={i}
              className="px-4 py-3 rounded-2xl bg-bloom-500/8 border border-bloom-500/20 flex items-start gap-3"
            >
              <div className="size-7 rounded-full bg-bloom-500/15 grid place-items-center shrink-0 mt-0.5">
                <Heart className="size-3.5 text-bloom-500 fill-bloom-500" />
              </div>
              <div className="text-[13px] leading-snug">
                <p className="font-semibold text-leaf-800">Message from Dr. Reyes</p>
                <p className="text-ink-muted">{m.text}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Chat thread */}
      <div ref={scrollRef} className="space-y-4 mb-4 max-h-[44vh] overflow-y-auto pr-1">
        {messages.map((m) => (
          <ChatBubble key={m.id} msg={m} />
        ))}
        {typing && (
          <div className="flex items-end gap-2">
            <Avatar />
            <div className="bg-sand-100 rounded-2xl rounded-bl-md px-4 py-3 flex gap-1">
              <Dot delay="0ms" />
              <Dot delay="150ms" />
              <Dot delay="300ms" />
            </div>
          </div>
        )}
      </div>

      {flagged && (
        <div className="mb-5 px-4 py-3 rounded-2xl bg-leaf-700/8 border border-leaf-700/15 flex items-start gap-3">
          <div className="size-7 rounded-full bg-leaf-700/15 grid place-items-center shrink-0 mt-0.5">
            <Check className="size-3.5 text-leaf-700" strokeWidth={3} />
          </div>
          <div className="text-[13px] leading-snug">
            <p className="font-semibold text-leaf-800">Sent to Dr. Reyes</p>
            <p className="text-ink-muted">Your care team has the full picture. No action needed from you.</p>
          </div>
        </div>
      )}

      {/* Quick suggestions — shown early in conversation */}
      {messages.length < 3 && !typing && (
        <div className="flex flex-wrap gap-2 mb-4">
          {["Feeling okay", "Mild headache", "Baby's been active"].map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setInput(s)}
              className="px-3 py-1.5 rounded-full bg-white border border-sand-200 text-[12px] font-medium text-leaf-800 hover:border-bloom-500/40 transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Composer — floats above the nav; the white gradient fades any
          content scrolling beneath it so the pill reads as floating */}
      <div className="fixed bottom-[108px] left-1/2 -translate-x-1/2 w-full max-w-[430px] z-10 px-5 pt-8 pb-2 bg-gradient-to-t from-white via-white to-transparent pointer-events-none">
        <form onSubmit={handleSend} className="pointer-events-auto">
          <div className="flex items-center gap-2 bg-white rounded-full pl-5 pr-1.5 py-1.5 shadow-lg shadow-bloom-500/15 ring-1 ring-sand-200/70">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Share how you're feeling…"
              className="flex-1 bg-transparent outline-none text-[14px] py-2 placeholder:text-ink/35"
            />
            <button
              type="submit"
              disabled={!input.trim() || sending}
              className="size-10 rounded-full bg-bloom-500 text-white grid place-items-center disabled:opacity-40 transition-opacity active:scale-95"
            >
              <Send className="size-4" />
            </button>
          </div>
        </form>
      </div>

      {/* Peek at next step */}
      <Link
        to="/watchfor"
        className="mt-6 flex items-center justify-between p-4 rounded-2xl bg-white border border-sand-100 hover:border-bloom-500/30 transition-colors"
      >
        <div>
          <p className="text-[11px] font-semibold text-bloom-600 uppercase tracking-wider mb-1">
            From your care plan
          </p>
          <p className="text-[14px] font-medium">Things to let me know about</p>
        </div>
        <ArrowRight className="size-4 text-ink/30" />
      </Link>
    </PatientShell>
  );
}

// ───────────────────────── Daily check-in panel ─────────────────────────

const SYMPTOMS = ["Headache", "Vision changes", "Swelling", "Upper belly pain", "Short of breath"];

function DailyCheckin({
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
    <section className="bg-white rounded-3xl border border-sand-200 shadow-sm p-5 mb-6">
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
                ? "No warning symptoms today — no headache, vision changes, swelling, belly pain, or shortness of breath."
                : `Today I'm noticing: ${list.join(", ").toLowerCase()}.`,
              { symptoms: list, symptomsDone: true },
            )
          }
        />
        <ChoiceRow
          label="Baby's movement"
          icon={<Baby className="size-4" />}
          value={
            checkin.movement
              ? checkin.movement === "normal"
                ? "Normal"
                : "Less than usual"
              : undefined
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
        className="w-[68px] text-center bg-white border border-sand-200 rounded-lg px-2 py-1.5 text-[13px] outline-none focus:border-bloom-500/50"
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

function ChatBubble({ msg }: { msg: Msg }) {
  if (msg.from === "maria") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] bg-bloom-500 text-white rounded-2xl rounded-br-md px-4 py-2.5 text-[14px] leading-snug shadow-sm">
          {msg.text}
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-end gap-2">
      <Avatar />
      <div className="max-w-[80%] bg-sand-100 text-ink rounded-2xl rounded-bl-md px-4 py-3 text-[14px] leading-relaxed">
        {msg.text}
      </div>
    </div>
  );
}

function Avatar() {
  return (
    <div className="size-7 rounded-full overflow-hidden ring-1 ring-bloom-500/20 shrink-0">
      <img src="/icon-192.png" alt="Cade" className="size-full object-cover" />
    </div>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="size-1.5 rounded-full bg-ink/30 animate-bounce"
      style={{ animationDelay: delay, animationDuration: "1s" }}
    />
  );
}
