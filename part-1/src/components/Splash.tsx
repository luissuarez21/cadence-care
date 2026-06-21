import { useEffect, useState } from "react";

/**
 * App-open splash: the Cade app-icon "pops" in over a violet wash, the
 * wordmark rises, then the whole overlay fades to reveal the app beneath.
 *
 * Rendered once per full page load (mounts with RootComponent). Client-side
 * route navigation does not remount it, so it won't replay on tab switches.
 */
export function Splash() {
  const [leaving, setLeaving] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const fade = setTimeout(() => setLeaving(true), 1700);
    const remove = setTimeout(() => setDone(true), 2250);
    return () => {
      clearTimeout(fade);
      clearTimeout(remove);
    };
  }, []);

  if (done) return null;

  return (
    <div
      aria-hidden
      className={
        "fixed inset-0 z-[100] grid place-items-center bg-gradient-to-b from-bloom-400 to-bloom-500 transition-opacity duration-500 ease-out " +
        (leaving ? "opacity-0" : "opacity-100")
      }
    >
      <div className="flex flex-col items-center">
        <img
          src="/icon-512.png"
          alt=""
          className="size-28 rounded-[30px] shadow-2xl shadow-black/20 ring-1 ring-white/30"
          style={{ animation: "cade-pop 0.65s cubic-bezier(0.34, 1.56, 0.64, 1) both" }}
        />
        <p
          className="mt-7 text-white text-[28px] font-serif font-semibold tracking-wide"
          style={{ animation: "cade-rise 0.6s ease-out 0.35s both" }}
        >
          Cadence
        </p>
        <p
          className="mt-1.5 text-white/85 text-[13px] font-medium tracking-wide"
          style={{ animation: "cade-rise 0.6s ease-out 0.55s both" }}
        >
          Hi, I&apos;m Cade
        </p>
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
      `}</style>
    </div>
  );
}
