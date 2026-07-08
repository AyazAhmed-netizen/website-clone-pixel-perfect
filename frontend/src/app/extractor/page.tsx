"use client";

import dynamic from "next/dynamic";

// Dynamic import to avoid SSR issues with browser-only components
const ExtractorPage = dynamic(
  () => import("@/components/extractor-page").then((mod) => ({ default: mod.PlaywrightPage })),
  { ssr: false }
);

/**
 * Extractor Route
 * 提取器路由页面
 */
export default function ExtractorRoute() {
  return <ExtractorPage />;
}
