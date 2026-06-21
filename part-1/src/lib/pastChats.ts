/**
 * Synthetic past conversations for the Chats list (demo).
 *
 * The backend seeds symptom logs, not chat threads, and we mint a fresh
 * session per load — so there is no real persisted chat history to list.
 * These are fully synthetic (Maria Chen, fictional) and power the read-only
 * past-chat view. The "today" conversation is the live agent, not from here.
 */

export type PastMsg = { from: "cadence" | "maria"; text: string };

export type PastChat = {
  id: string;
  title: string;
  dateLabel: string;
  preview: string;
  flagged?: boolean;
  messages: PastMsg[];
};

export const PAST_CHATS: PastChat[] = [
  {
    id: "2026-06-20",
    title: "Evening check-in",
    dateLabel: "Yesterday",
    preview: "Both readings look good tonight — nicely done.",
    messages: [
      { from: "cadence", text: "Evening, Maria. How are you feeling tonight?" },
      { from: "maria", text: "Pretty good, a little tired." },
      { from: "cadence", text: "That's completely normal at 28 weeks. What did your blood pressure read?" },
      { from: "maria", text: "128/82" },
      { from: "cadence", text: "Both readings look good tonight — nicely done. Get some rest, and I'll check in tomorrow." },
    ],
  },
  {
    id: "2026-06-18",
    title: "Headache mention",
    dateLabel: "Wed",
    preview: "I've noted the headache for Dr. Reyes to review.",
    flagged: true,
    messages: [
      { from: "cadence", text: "Good afternoon, Maria. How's your day going?" },
      { from: "maria", text: "I had a headache earlier, around a 4 out of 10." },
      { from: "cadence", text: "Thank you for telling me. Any changes in your vision — flashing lights or blurriness?" },
      { from: "maria", text: "No, just the headache." },
      { from: "cadence", text: "Okay. I've noted the headache for Dr. Reyes to review at your visit. Let me know if it comes back or gets worse." },
    ],
  },
  {
    id: "2026-06-15",
    title: "Morning check-in",
    dateLabel: "Sun",
    preview: "Thanks for logging both readings and your aspirin.",
    messages: [
      { from: "cadence", text: "Good morning! Ready for today's check-in?" },
      { from: "maria", text: "Yep. BP was 124/79." },
      { from: "cadence", text: "Great. Did you take your low-dose aspirin?" },
      { from: "maria", text: "Yes, with breakfast." },
      { from: "cadence", text: "Thanks for logging both readings and your aspirin. You're staying right on track." },
    ],
  },
];

export function getPastChat(id: string): PastChat | undefined {
  return PAST_CHATS.find((c) => c.id === id);
}
