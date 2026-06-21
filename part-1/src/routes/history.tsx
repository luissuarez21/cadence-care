import { createFileRoute } from "@tanstack/react-router";
import { Check } from "lucide-react";
import { PatientShell } from "@/components/PatientShell";

export const Route = createFileRoute("/history")({
  head: () => ({
    meta: [
      { title: "History — Cadence" },
      { name: "description", content: "Your check-in history." },
    ],
  }),
  component: HistoryPage,
});

const entries = [
  { day: "Today", date: "Oct 24", bp: "142 / 91", note: "Shared with Dr. Reyes", flag: true },
  { day: "Yesterday", date: "Oct 23", bp: "128 / 84", note: "Mild headache, eased after rest" },
  { day: "Mon", date: "Oct 22", bp: "126 / 82", note: "Feeling rested" },
  { day: "Sun", date: "Oct 21", bp: "124 / 80", note: "Walked 20 min" },
  { day: "Sat", date: "Oct 20", bp: "130 / 84", note: "Good day overall" },
  { day: "Fri", date: "Oct 19", bp: "128 / 83", note: "Baby active in evening" },
  { day: "Thu", date: "Oct 18", bp: "127 / 81", note: "Took prenatal vitamins" },
  { day: "Wed", date: "Oct 17", bp: "129 / 84", note: "Feeling okay" },
  { day: "Tue", date: "Oct 16", bp: "125 / 80", note: "Slept well" },
];

function HistoryPage() {
  return (
    <PatientShell eyebrow="Your check-ins" title="A gentle log">
      <section className="bg-sand-100 rounded-[28px] p-5 mb-6 border border-black/[0.04]">
        <div className="flex items-baseline gap-3 mb-1">
          <span className="font-serif text-4xl font-semibold text-leaf-800">9</span>
          <span className="text-[13px] text-ink-muted">check-ins this week</span>
        </div>
        <div className="flex items-center gap-2 mt-3">
          <div className="size-6 rounded-full bg-leaf-700/15 grid place-items-center">
            <Check className="size-3 text-leaf-700" strokeWidth={3} />
          </div>
          <p className="text-[13px] text-leaf-800 font-medium">
            One pattern flagged. Dr. Reyes has been notified.
          </p>
        </div>
      </section>

      <h3 className="text-[11px] font-semibold text-ink-muted uppercase tracking-widest mb-4 px-1">
        Timeline
      </h3>

      <div className="relative">
        <div className="absolute left-[11px] top-2 bottom-2 w-px bg-sand-200" />
        <div className="space-y-4">
          {entries.map((e) => (
            <div key={e.date} className="relative pl-9">
              <div
                className={
                  "absolute left-0 top-1.5 size-[22px] rounded-full grid place-items-center " +
                  (e.flag ? "bg-bloom-500" : "bg-white border-2 border-sand-200")
                }
              >
                {e.flag && <span className="size-1.5 rounded-full bg-white" />}
              </div>
              <div className="bg-white border border-sand-100 rounded-2xl p-4">
                <div className="flex justify-between items-baseline mb-1.5">
                  <span className="font-semibold text-[14px] text-leaf-800">
                    {e.day} <span className="text-ink/40 font-normal">· {e.date}</span>
                  </span>
                  <span className="font-serif text-[15px] text-ink">{e.bp}</span>
                </div>
                <p className="text-[13px] text-ink-muted leading-snug">{e.note}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </PatientShell>
  );
}
