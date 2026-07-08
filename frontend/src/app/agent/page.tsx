"use client";

import dynamic from "next/dynamic";

// Dynamic import to avoid SSR issues
const BoxLiteAgentPage = dynamic(
  () => import("@/components/boxlite/boxlite-agent-page").then((mod) => mod.default),
  { ssr: false }
);

/**
 * Agent Route
 * Backend sandbox-based AI agent page
 *
 * All sandbox operations run on the backend using BoxLite.
 */
export default function AgentRoute() {
  return <BoxLiteAgentPage />;
}
