import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Eye,
  HeartPulse,
  Droplets,
  Baby,
  Zap,
  Pill,
  Scale,
  Stethoscope,
  ChevronDown,
  type LucideIcon,
} from "lucide-react";
import { PatientShell } from "@/components/PatientShell";
import { api, PATIENT_ID } from "@/lib/api";

export const Route = createFileRoute("/watchfor")({
  head: () => ({
    meta: [
      { title: "Things to Watch For — Cadence" },
      { name: "description", content: "What to let Cadence know about right away." },
    ],
  }),
  component: WatchForPage,
});

type RedFlag = {
  description: string;
  severity: "ok" | "monitor" | "escalate" | "escalate_urgent";
  escalation_message: string;
};

type WatchForResponse = {
  patient_id: string;
  red_flags: RedFlag[];
};

// Themed categories. Each raw red flag is matched to the FIRST category whose
// `match` returns true, so order matters (e.g. swelling before blood pressure,
// since "swelling AND elevated BP" should live under Swelling).
type Category = {
  key: string;
  icon: LucideIcon;
  title: string;
  subtitle: string;
  match: (d: string) => boolean;
};

const CATEGORIES: Category[] = [
  {
    key: "swelling",
    icon: Droplets,
    title: "Swelling",
    subtitle: "New puffiness in your face or hands",
    match: (d) => /swelling|facial|edema|hand/.test(d),
  },
  {
    key: "headache_vision",
    icon: Eye,
    title: "Headaches or vision",
    subtitle: "A bad headache, or changes in your vision",
    match: (d) => /headache|head|vision|visual|blurred|spots|flashing/.test(d),
  },
  {
    key: "bp",
    icon: HeartPulse,
    title: "Blood pressure",
    subtitle: "A reading that's higher than usual",
    match: (d) => /\bbp\b|blood pressure|systolic|diastolic/.test(d),
  },
  {
    key: "movement",
    icon: Baby,
    title: "Baby's movement",
    subtitle: "Moving less than your normal",
    match: (d) => /fetal|movement|kick/.test(d),
  },
  {
    key: "contractions",
    icon: Zap,
    title: "Early contractions",
    subtitle: "Regular tightening before 37 weeks",
    match: (d) => /contraction|preterm|labor|gestation/.test(d),
  },
  {
    key: "belly",
    icon: Stethoscope,
    title: "Upper belly pain",
    subtitle: "Pain high up under your ribs",
    match: (d) => /abdominal|quadrant|rib|epigastric/.test(d),
  },
  {
    key: "weight",
    icon: Scale,
    title: "Weight",
    subtitle: "A quick jump on the scale",
    match: (d) => /weight|gain/.test(d),
  },
  {
    key: "aspirin",
    icon: Pill,
    title: "Your aspirin",
    subtitle: "Keeping up with your daily dose",
    match: (d) => /aspirin|dose|medication/.test(d),
  },
];

// Render math operators as proper glyphs (≥ / ≤) instead of ">=" / "<=".
function tidySymbols(d: string): string {
  return d.replace(/>=/g, "≥").replace(/<=/g, "≤");
}

// Plain-language rewrite of a clinical red-flag string. Falls back to the
// original text (with tidied symbols) for anything we don't recognize.
function plainify(d: string): string {
  const s = d.toLowerCase();
  if (/headache/.test(s) && /(vision|visual|blurred|spots|flashing)/.test(s))
    return "A bad headache together with vision changes";
  if (/headache/.test(s)) return "A bad headache that won't ease up";
  if (/(vision|visual|blurred|spots|flashing)/.test(s))
    return "New blurriness, spots, or flashing lights";
  if (/swelling|facial|edema|hand/.test(s)) return "New puffiness in your face or hands";
  if (/(160|110)/.test(s)) return "One reading in the high range";
  if (/\bbp\b|blood pressure|systolic|diastolic/.test(s))
    return "Two higher-than-usual readings in a day";
  if (/fetal|movement|kick/.test(s)) return "Baby moving less than usual";
  if (/contraction|preterm|labor|gestation/.test(s))
    return "Regular tightening before 37 weeks";
  if (/abdominal|quadrant|rib|epigastric/.test(s)) return "Pain high up under your ribs";
  if (/weight|gain/.test(s)) return "Gaining weight quickly (about 5 lb in a week)";
  if (/aspirin|dose|medication/.test(s)) return "Missing your aspirin a couple days running";
  return tidySymbols(d);
}

function WatchForPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["watchfor", PATIENT_ID],
    queryFn: () => api.get<WatchForResponse>("/patient/watchfor"),
  });

  // Bucket the raw flags into categories, preserving CATEGORIES order.
  const groups = CATEGORIES.map((cat) => ({
    cat,
    flags: (data?.red_flags ?? []).filter(
      (f) => CATEGORIES.find((c) => c.match(f.description.toLowerCase()))?.key === cat.key,
    ),
  })).filter((g) => g.flags.length > 0);

  return (
    <PatientShell eyebrow="From your care plan" title="Things to watch for">
      <p className="text-[14px] text-ink-muted leading-relaxed mb-6 font-serif">
        A few things Dr. Reyes wants me to keep an eye on. Nothing here means something's
        wrong — just tap any one to see what I'd do.
      </p>

      {isLoading && (
        <div className="space-y-2.5">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-white p-4 rounded-2xl border border-sand-100 flex items-center gap-4 animate-pulse">
              <div className="size-11 rounded-xl bg-sand-100 shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3.5 bg-sand-100 rounded w-1/3" />
                <div className="h-3 bg-sand-100 rounded w-3/5" />
              </div>
            </div>
          ))}
        </div>
      )}

      {isError && (
        <p className="text-[14px] text-ink-muted text-center py-8">
          Couldn't load your care plan right now. Try again in a moment.
        </p>
      )}

      {data && (
        <div className="space-y-2.5">
          {groups.map(({ cat, flags }) => (
            <CategoryCard key={cat.key} cat={cat} flags={flags} />
          ))}
        </div>
      )}

      <div className="mt-8 p-5 rounded-2xl bg-leaf-800 text-white relative overflow-hidden">
        <div className="absolute -right-10 -bottom-10 size-32 bg-leaf-700/60 rounded-full blur-3xl" />
        <p className="text-[11px] font-semibold uppercase tracking-widest text-white/60 mb-2">
          A note from Cadence
        </p>
        <p className="font-serif text-[16px] leading-snug relative">
          You don't need to memorize this. I check in with you every day, and if anything
          matches, I'll know exactly what to do.
        </p>
      </div>
    </PatientShell>
  );
}

function CategoryCard({ cat, flags }: { cat: Category; flags: RedFlag[] }) {
  const [open, setOpen] = useState(false);
  const Icon = cat.icon;
  // Plain, de-duplicated list of the specific signs in this category.
  const signs = [...new Set(flags.map((f) => plainify(f.description)))];

  return (
    <div className="bg-white rounded-2xl border border-sand-100 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full p-4 flex items-center gap-4 text-left"
      >
        <div className="size-11 rounded-xl grid place-items-center shrink-0 bg-bloom-500/10 text-bloom-600">
          <Icon className="size-5" strokeWidth={2} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-[14px] text-leaf-800">{cat.title}</p>
          <p className="text-[13px] text-ink-muted leading-snug">{cat.subtitle}</p>
        </div>
        <ChevronDown
          className={"size-4 text-ink/30 shrink-0 transition-transform " + (open ? "rotate-180" : "")}
        />
      </button>

      {open && (
        <div className="px-4 pb-4 pt-0 ml-[60px]">
          <ul className="space-y-1.5 mb-3">
            {signs.map((s) => (
              <li key={s} className="flex items-start gap-2 text-[13px] text-leaf-800">
                <span className="mt-1.5 size-1.5 rounded-full bg-bloom-500/60 shrink-0" />
                {s}
              </li>
            ))}
          </ul>
          <p className="text-[12.5px] text-ink-muted leading-relaxed border-t border-sand-100 pt-2.5">
            If this comes up, I'll note it and share it with Dr. Reyes — no action needed from you.
          </p>
        </div>
      )}
    </div>
  );
}
