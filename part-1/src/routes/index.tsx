import { createFileRoute } from "@tanstack/react-router";
import { LiveChat } from "@/components/Conversation";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Cade — Cadence" },
      { name: "description", content: "Your daily check-in with Cade." },
    ],
  }),
  component: LiveChat,
});
