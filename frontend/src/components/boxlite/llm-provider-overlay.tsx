"use client";

import React from "react";
import LLMProviderSettingsCard from "@/components/agent/llm-provider-settings-card";

export function LLMProviderOverlay() {
  return (
    <div
      style={{
        position: "absolute",
        top: 12,
        right: 12,
        zIndex: 50,
        width: 360,
        pointerEvents: "auto",
      }}
    >
      <LLMProviderSettingsCard />
    </div>
  );
}

