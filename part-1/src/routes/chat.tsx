import { createFileRoute, Navigate } from "@tanstack/react-router";
import { PastChatView } from "@/components/Conversation";
import { getPastChat } from "@/lib/pastChats";

export const Route = createFileRoute("/chat")({
  validateSearch: (s: Record<string, unknown>): { sid?: string } => ({
    sid: typeof s.sid === "string" ? s.sid : undefined,
  }),
  head: () => ({
    meta: [{ title: "Conversation — Cadence" }],
  }),
  component: PastChatPage,
});

function PastChatPage() {
  const { sid } = Route.useSearch();
  const past = sid ? getPastChat(sid) : undefined;
  // The live chat lives at "/"; /chat is only for viewing a past thread.
  if (!past) return <Navigate to="/" />;
  return <PastChatView title={past.title} messages={past.messages} />;
}
