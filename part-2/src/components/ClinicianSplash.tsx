import { useEffect, useState } from "react";

interface Props {
  loading: boolean;
}

export function ClinicianSplash({ loading }: Props) {
  const [leaving, setLeaving] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (loading) return;
    const fade = setTimeout(() => setLeaving(true), 300);
    const remove = setTimeout(() => setDone(true), 800);
    return () => { clearTimeout(fade); clearTimeout(remove); };
  }, [loading]);

  if (done) return null;

  return (
    <div
      aria-hidden
      className={`fixed inset-0 z-[100] grid place-items-center transition-opacity duration-500 ease-out ${
        leaving ? "opacity-0 pointer-events-none" : "opacity-100"
      }`}
      style={{
        background: "linear-gradient(160deg, oklch(0.88 0.07 305) 0%, oklch(0.72 0.16 305) 100%)",
      }}
    >
      <div className="flex flex-col items-center">
        <img
          src="/icon-512.png"
          alt=""
          className="w-24 h-24 rounded-[26px] shadow-2xl shadow-black/25 ring-2 ring-white/20"
          style={{ animation: "cade-pop 0.65s cubic-bezier(0.34,1.56,0.64,1) both" }}
        />
        <div
          className="mt-6 text-center"
          style={{ animation: "cade-rise 0.6s ease-out 0.35s both" }}
        >
          <p className="text-white text-[26px] font-display font-semibold tracking-tight">
            Cadence
          </p>
          <p className="text-white/65 text-[11px] font-semibold tracking-[0.2em] uppercase mt-1">
            Clinician Portal
          </p>
        </div>

        {loading && (
          <div
            className="mt-8 flex gap-1.5"
            style={{ animation: "cade-rise 0.5s ease-out 0.6s both" }}
          >
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-white/50"
                style={{ animation: `cade-dot 1.2s ease-in-out ${i * 0.2}s infinite` }}
              />
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes cade-pop {
          0%   { transform: scale(0.35); opacity: 0; }
          60%  { transform: scale(1.08); opacity: 1; }
          100% { transform: scale(1); opacity: 1; }
        }
        @keyframes cade-rise {
          from { transform: translateY(10px); opacity: 0; }
          to   { transform: translateY(0); opacity: 1; }
        }
        @keyframes cade-dot {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.35; }
          40%            { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
