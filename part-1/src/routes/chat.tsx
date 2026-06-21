import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Send, Heart, ChevronLeft } from "lucide-react";
import { toast } from "sonner";
import { PatientShell } from "@/components/PatientShell";
import { api, PATIENT_ID } from "@/lib/api";
import { getPastChat, type PastMsg } from "@/lib/pastChats";

export const Route = createFileRoute("/chat")({
  validateSearch: (s: Record<string, unknown>): { sid?: string } => ({
    sid: typeof s.sid === "string" ? s.sid : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Cade — Cadence" },
      { name: "description", content: "Chat with Cade, your daily companion." },
    ],
  }),
  component: ChatPage,
});

type Msg = { id: number; from: "cadence" | "maria"; text: string; flagged?: boolean };

const GREETING: Msg = {
  id: 0,
  from: "cadence",
  text: "Good afternoon, Maria. How are you feeling today? Take your time — tell me whatever's on your mind.",
};

type CareMessage = { text: string; timestamp: string };

function ChatPage() {
  const { sid } = Route.useSearch();
  const past = sid ? getPastChat(sid) : undefined;
  if (past) return <PastChatView title={past.title} messages={past.messages} />;
  return <LiveChat />;
}

function LiveChat() {
  const [sessionId] = useState(() =>
    typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `s-${Date.now()}`,
  );
  const [messages, setMessages] = useState<Msg[]>([GREETING]);
  const [careMessages, setCareMessages] = useState<CareMessage[]>([]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .get<{ messages: Array<{ sender: string; text: string; flagged?: boolean }> }>(
        `/chat/history?session_id=${sessionId}`,
      )
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
      .catch(() => {});

    api
      .get<{ messages: Array<{ text: string; timestamp: string }> }>("/patient/messages")
      .then((res) => setCareMessages(res.messages))
      .catch(() => {});

    inputRef.current?.focus();
  }, [sessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setMessages((m) => [...m, { id: Date.now(), from: "maria", text }]);
    setInput("");
    setSending(true);
    setTyping(true);
    try {
      const res = await api.post<{ reply: string; flagged: boolean }>("/chat/message", {
        patient_id: PATIENT_ID,
        message: text,
        session_id: sessionId,
      });
      setTyping(false);
      setMessages((m) => [
        ...m,
        { id: Date.now() + 1, from: "cadence", text: res.reply, flagged: res.flagged },
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
    <PatientShell eyebrow="Chat with" title="Cade">
      <ChatHeader />

      {careMessages.length > 0 && (
        <div className="mb-5 space-y-2">
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

      <div ref={scrollRef} className="space-y-4 mb-4 max-h-[56vh] overflow-y-auto pr-1">
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
    </PatientShell>
  );
}

function PastChatView({ title, messages }: { title: string; messages: PastMsg[] }) {
  return (
    <PatientShell eyebrow="Earlier" title={title}>
      <ChatHeader />
      <div className="space-y-4 mb-4">
        {messages.map((m, i) => (
          <ChatBubble key={i} msg={{ id: i, from: m.from, text: m.text }} />
        ))}
      </div>
      <p className="text-center text-[12px] text-ink/40 mt-6">This conversation has ended.</p>
    </PatientShell>
  );
}

function ChatHeader() {
  return (
    <Link
      to="/"
      className="inline-flex items-center gap-1 text-[13px] font-medium text-leaf-700 hover:text-bloom-600 transition-colors mb-4 -ml-1"
    >
      <ChevronLeft className="size-4" />
      Chats
    </Link>
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

function Avatar({ size = 7 }: { size?: 7 | 9 }) {
  return (
    <div
      className={
        (size === 9 ? "size-9" : "size-7") +
        " rounded-full overflow-hidden ring-1 ring-bloom-500/20 shrink-0"
      }
    >
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
