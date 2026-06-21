import { createFileRoute } from "@tanstack/react-router";
import { Share2, Calendar } from "lucide-react";
import { PatientShell } from "@/components/PatientShell";

export const Route = createFileRoute("/summary")({
  head: () => ({
    meta: [
      { title: "Visit Summary — Cadence" },
      { name: "description", content: "What to bring to your next appointment." },
    ],
  }),
  component: SummaryPage,
});

function SummaryPage() {
  return (
    <PatientShell eyebrow="Take to your visit" title="Your Oct 30 brief">
      <section className="bg-leaf-800 text-white rounded-[28px] p-6 relative overflow-hidden mb-6">
        <div className="absolute -right-8 -bottom-12 size-40 bg-leaf-700/60 rounded-full blur-3xl" />
        <div className="relative">
          <div className="flex items-center gap-2 mb-3">
            <Calendar className="size-4 text-bloom-400" />
            <span className="text-[12px] font-semibold uppercase tracking-widest text-white/70">
              Next appointment
            </span>
          </div>
          <p className="font-serif text-2xl leading-tight mb-1">Wed, Oct 30 · 10:30 AM</p>
          <p className="text-white/70 text-[13px]">Dr. Reyes · MFM Clinic, Suite 4B</p>
          <div className="mt-5 flex gap-1.5">
            <div className="h-1 flex-1 bg-white/15 rounded-full overflow-hidden">
              <div className="h-full w-[85%] bg-bloom-400 rounded-full" />
            </div>
          </div>
          <p className="text-[11px] text-white/60 mt-2">9 of 11 daily check-ins complete</p>
        </div>
      </section>

      <div className="space-y-5">
        <Block label="What I noticed">
          <p>
            Your blood pressure stayed in a healthy range most days, with one
            reading above your target on{" "}
            <span className="font-semibold text-leaf-800">Oct 24 (142/91)</span>{" "}
            that I shared with Dr. Reyes. You mentioned a mild headache on three
            days, easing with rest.
          </p>
        </Block>

        <Block label="What's going well">
          <ul className="space-y-1.5">
            <Bullet>Consistent daily check-ins — every morning this week.</Bullet>
            <Bullet>Baby's movement has been regular and active in the evenings.</Bullet>
            <Bullet>You're taking your prenatal vitamin every day.</Bullet>
          </ul>
        </Block>

        <Block label="Questions you might ask Dr. Reyes">
          <ul className="space-y-1.5">
            <Bullet>Should I be tracking blood pressure twice a day now?</Bullet>
            <Bullet>What does the recent reading mean for the rest of my pregnancy?</Bullet>
            <Bullet>Is there anything else I should be watching for at 28 weeks?</Bullet>
          </ul>
        </Block>
      </div>

      <button className="mt-7 w-full bg-bloom-500 hover:bg-bloom-600 text-white font-semibold py-4 rounded-2xl shadow-lg shadow-bloom-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2">
        <Share2 className="size-4" />
        Share this brief with my doctor
      </button>
      <p className="text-center text-[11px] text-ink-muted mt-3">
        A copy is already in Dr. Reyes' inbox.
      </p>
    </PatientShell>
  );
}

function Block({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-sand-100 rounded-2xl p-5">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-bloom-600 mb-2">
        {label}
      </p>
      <div className="text-[14px] text-ink leading-relaxed font-serif">{children}</div>
    </div>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex gap-2.5">
      <span className="mt-2 size-1.5 rounded-full bg-leaf-700 shrink-0" />
      <span>{children}</span>
    </li>
  );
}
