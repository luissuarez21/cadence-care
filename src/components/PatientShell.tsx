import { Link, useRouterState } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { MessageCircle, ListChecks, BookOpen, FileText } from "lucide-react";

const tabs = [
  { to: "/", label: "Today", icon: MessageCircle },
  { to: "/watchfor", label: "Watch For", icon: ListChecks },
  { to: "/history", label: "History", icon: BookOpen },
  { to: "/summary", label: "Visit", icon: FileText },
] as const;

interface ShellProps {
  children: ReactNode;
  eyebrow?: string;
  title?: string;
}

export function PatientShell({ children, eyebrow = "Good Morning", title = "Maria Chen" }: ShellProps) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <div className="min-h-screen bg-sand-50 font-sans text-ink flex justify-center">
      <div className="w-full max-w-[430px] bg-white min-h-screen shadow-2xl shadow-sand-200/60 flex flex-col relative">
        <header className="pt-12 px-6 pb-6 flex justify-between items-center shrink-0">
          <div>
            <h2 className="text-[12px] font-semibold text-leaf-700 uppercase tracking-[0.18em] mb-1">
              {eyebrow}
            </h2>
            <h1 className="text-3xl font-serif font-semibold leading-tight">{title}</h1>
          </div>
          <div className="size-12 rounded-full bg-sand-100 outline-1 outline-offset-2 outline-bloom-500/30 grid place-items-center text-leaf-800 font-serif text-base">
            MC
          </div>
        </header>

        <main className="flex-1 px-6 pb-36">{children}</main>

        <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[430px] bg-white/85 backdrop-blur-xl border-t border-sand-100 px-6 pt-3 pb-7 flex justify-between items-center z-20">
          {tabs.map(({ to, label, icon: Icon }) => {
            const active = pathname === to;
            return (
              <Link
                key={to}
                to={to}
                className="flex flex-col items-center gap-1.5 flex-1"
              >
                <div
                  className={
                    "size-9 rounded-xl grid place-items-center transition-colors " +
                    (active
                      ? "bg-bloom-500/12 text-bloom-600 ring-1 ring-bloom-500/40"
                      : "text-ink/35")
                  }
                >
                  <Icon className="size-[18px]" strokeWidth={active ? 2.4 : 2} />
                </div>
                <span
                  className={
                    "text-[10px] font-semibold uppercase tracking-wider " +
                    (active ? "text-bloom-600" : "text-ink/40")
                  }
                >
                  {label}
                </span>
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
