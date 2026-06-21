import { createFileRoute, Link } from "@tanstack/react-router";
import { ChevronRight, Sparkles } from "lucide-react";
import { PatientShell } from "@/components/PatientShell";
import { PAST_CHATS } from "@/lib/pastChats";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Chats — Cadence" },
      { name: "description", content: "Your conversations with Cade." },
    ],
  }),
  component: ChatsPage,
});

function ChatsPage() {
  return (
    <PatientShell eyebrow="Good Afternoon" title="Maria Chen">
      {/* Today — the live conversation */}
      <Link
        to="/chat"
        className="flex items-center gap-3.5 p-4 rounded-3xl bg-bloom-500 text-white shadow-lg shadow-bloom-500/25 mb-4 active:scale-[0.99] transition-transform"
      >
        <div className="size-12 rounded-full overflow-hidden ring-2 ring-white/40 shrink-0">
          <img src="/icon-192.png" alt="Cade" className="size-full object-cover" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="text-[15px] font-semibold">Today with Cade</p>
            <Sparkles className="size-3.5 text-white/80" />
          </div>
          <p className="text-[13px] text-white/85 truncate">Tap to start your check-in chat</p>
        </div>
        <ChevronRight className="size-5 text-white/70 shrink-0" />
      </Link>

      {/* Past conversations */}
      <p className="text-[11px] font-semibold text-ink/40 uppercase tracking-wider px-1 mb-2 mt-6">
        Earlier
      </p>
      <div className="space-y-2">
        {PAST_CHATS.map((c) => (
          <Link
            key={c.id}
            to="/chat"
            search={{ sid: c.id }}
            className="flex items-center gap-3.5 p-3.5 rounded-2xl bg-white border border-sand-100 hover:border-bloom-500/30 transition-colors"
          >
            <div className="size-11 rounded-full overflow-hidden ring-1 ring-bloom-500/15 shrink-0">
              <img src="/icon-192.png" alt="" className="size-full object-cover" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[14px] font-semibold text-leaf-800 truncate">{c.title}</p>
                <span className="text-[11px] text-ink/40 shrink-0">{c.dateLabel}</span>
              </div>
              <div className="flex items-center gap-1.5">
                {c.flagged && <span className="size-1.5 rounded-full bg-bloom-500 shrink-0" />}
                <p className="text-[13px] text-ink-muted truncate">{c.preview}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </PatientShell>
  );
}
