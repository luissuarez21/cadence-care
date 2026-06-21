import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Send, Heart, ArrowRight, Check } from "lucide-react";
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
  text: "Good morning, Maria. How are you feeling today? When you're ready, share your blood pressure reading.",
};

type CareMessage = { text: string; timestamp: string };

function TodayPage() {
  const [messages, setMessages] = useState<Msg[]>([GREETING]);
  const [careMessages, setCareMessages] = useState<CareMessage[]>([]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Rehydrate thread from history on mount
  useEffect(() => {
    api
      .get<{ patient_id: string; session_id: string; messages: Array<{ sender: string; text: string; timestamp: string; flagged?: boolean }> }>("/chat/history")
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
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing]);

  const flagged = messages.some((m) => m.flagged);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: Msg = { id: Date.now(), from: "maria", text };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setSending(true);
    setTyping(true);

    try {
      const res = await api.post<{ reply: string; flagged: boolean; risk?: unknown }>("/chat/message", {
        patient_id: PATIENT_ID,
        message: text,
      });
      setTyping(false);
      setMessages((m) => [
        ...m,
        {
          id: Date.now() + 1,
          from: "cadence",
          text: res.reply,
          flagged: res.flagged,
        },
      ]);
    } catch {
      setTyping(false);
      setInput(text);
      toast.error("Couldn't reach Cadence — please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <PatientShell>
      {/* Day card */}
      <section className="bg-sand-100 rounded-[28px] p-5 border border-black/[0.04] mb-6">
        <div className="flex items-center justify-between mb-1">
          <span className="inline-flex items-center gap-1.5 bg-white px-3 py-1 rounded-full text-[11px] font-semibold text-leaf-800 border border-leaf-700/10">
            <Heart className="size-3 text-bloom-500 fill-bloom-500" />
            Daily Check-in
          </span>
          <span className="text-ink/40 text-[11px] font-medium">Week 28 · Day 9</span>
        </div>
        <p className="text-[15px] text-leaf-800/90 leading-relaxed mt-3 font-serif">
          Nine check-ins this week. No red flags so far — you're doing beautifully.
        </p>
      </section>

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
          {["142/91", "Feeling okay", "Mild headache"].map((s) => (
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

      {/* Composer */}
      <form
        onSubmit={handleSend}
        className="fixed bottom-24 left-1/2 -translate-x-1/2 w-full max-w-[430px] px-6"
      >
        <div className="flex items-center gap-2 bg-white border border-sand-200 rounded-full pl-5 pr-1.5 py-1.5 shadow-sm">
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
    <div className="size-7 rounded-full bg-leaf-700 grid place-items-center shrink-0">
      <span className="text-white text-[10px] font-semibold tracking-wider font-serif">C</span>
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
