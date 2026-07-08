"use client";

import React from "react";
import { cn } from "@/lib/utils";
import type { PlatformType } from "@/lib/prompt-templates";

// ============================================
// Platform Icon Props
// ============================================

interface PlatformIconProps {
  platform: PlatformType;
  className?: string;
  size?: number;
}

// ============================================
// Bolt.new (StackBlitz) Icon
// ============================================

function BoltIcon({ className, size = 20 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      className={className}
      fill="currentColor"
    >
      <path d="M10.797 14.182H3.635L16.728 0l-3.525 9.818h7.162L7.272 24l3.524-9.818Z" />
    </svg>
  );
}

// ============================================
// Claude AI Icon
// ============================================

function ClaudeIcon({ className, size = 20 }: { className?: string; size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 509.64"
      width={size}
      height={size}
      className={className}
    >
      <path
        fill="#D77655"
        d="M115.612 0h280.775C459.974 0 512 52.026 512 115.612v278.415c0 63.587-52.026 115.612-115.613 115.612H115.612C52.026 509.639 0 457.614 0 394.027V115.612C0 52.026 52.026 0 115.612 0z"
      />
      <path
        fill="#FCF2EE"
        fillRule="nonzero"
        d="M142.27 316.619l73.655-41.326 1.238-3.589-1.238-1.996-3.589-.001-12.31-.759-42.084-1.138-36.498-1.516-35.361-1.896-8.897-1.895-8.34-10.995.859-5.484 7.482-5.03 10.717.935 23.683 1.617 35.537 2.452 25.782 1.517 38.193 3.968h6.064l.86-2.451-2.073-1.517-1.618-1.517-36.776-24.922-39.81-26.338-20.852-15.166-11.273-7.683-5.687-7.204-2.451-15.721 10.237-11.273 13.75.935 3.513.936 13.928 10.716 29.749 23.027 38.848 28.612 5.687 4.727 2.275-1.617.278-1.138-2.553-4.271-21.13-38.193-22.546-38.848-10.035-16.101-2.654-9.655c-.935-3.968-1.617-7.304-1.617-11.374l11.652-15.823 6.445-2.073 15.545 2.073 6.547 5.687 9.655 22.092 15.646 34.78 24.265 47.291 7.103 14.028 3.791 12.992 1.416 3.968 2.449-.001v-2.275l1.997-26.641 3.69-32.707 3.589-42.084 1.239-11.854 5.863-14.206 11.652-7.683 9.099 4.348 7.482 10.716-1.036 6.926-4.449 28.915-8.72 45.294-5.687 30.331h3.313l3.792-3.791 15.342-20.372 25.782-32.227 11.374-12.789 13.27-14.129 8.517-6.724 16.1-.001 11.854 17.617-5.307 18.199-16.581 21.029-13.75 17.819-19.716 26.54-12.309 21.231 1.138 1.694 2.932-.278 44.536-9.479 24.062-4.347 28.714-4.928 12.992 6.066 1.416 6.167-5.106 12.613-30.71 7.583-36.018 7.204-53.636 12.689-.657.48.758.935 24.164 2.275 10.337.556h25.301l47.114 3.514 12.309 8.139 7.381 9.959-1.238 7.583-18.957 9.655-25.579-6.066-59.702-14.205-20.474-5.106-2.83-.001v1.694l17.061 16.682 31.266 28.233 39.152 36.397 1.997 8.999-5.03 7.102-5.307-.758-34.401-25.883-13.27-11.651-30.053-25.302-1.996-.001v2.654l6.926 10.136 36.574 54.975 1.895 16.859-2.653 5.485-9.479 3.311-10.414-1.895-21.408-30.054-22.092-33.844-17.819-30.331-2.173 1.238-10.515 113.261-4.929 5.788-11.374 4.348-9.478-7.204-5.03-11.652 5.03-23.027 6.066-30.052 4.928-23.886 4.449-29.674 2.654-9.858-.177-.657-2.173.278-22.37 30.71-34.021 45.977-26.919 28.815-6.445 2.553-11.173-5.789 1.037-10.337 6.243-9.2 37.257-47.392 22.47-29.371 14.508-16.961-.101-2.451h-.859l-98.954 64.251-17.618 2.275-7.583-7.103.936-11.652 3.589-3.791 29.749-20.474-.101.102.024.101z"
      />
    </svg>
  );
}

// ============================================
// Cursor AI Icon (3D Cube)
// ============================================

function CursorIcon({ className, size = 20 }: { className?: string; size?: number }) {
  return (
    <svg
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 512"
      width={size}
      height={size}
      className={className}
    >
      <g clipPath="url(#cursor-clip0)">
        <rect width="512" height="512" rx="122" fill="#000" />
        <g clipPath="url(#cursor-clip1)">
          <mask
            id="cursor-mask"
            style={{ maskType: "luminance" }}
            maskUnits="userSpaceOnUse"
            x="85"
            y="89"
            width="343"
            height="334"
          >
            <path d="M85 89h343v334H85V89z" fill="#fff" />
          </mask>
          <g mask="url(#cursor-mask)">
            <path
              d="M255.428 423l148.991-83.5L255.428 256l-148.99 83.5 148.99 83.5z"
              fill="url(#cursor-grad0)"
            />
            <path
              d="M404.419 339.5v-167L255.428 89v167l148.991 83.5z"
              fill="url(#cursor-grad1)"
            />
            <path
              d="M255.428 89l-148.99 83.5v167l148.99-83.5V89z"
              fill="url(#cursor-grad2)"
            />
            <path d="M404.419 172.5L255.428 423V256l148.991-83.5z" fill="#E4E4E4" />
            <path d="M404.419 172.5L255.428 256l-148.99-83.5h297.981z" fill="#fff" />
          </g>
        </g>
      </g>
      <defs>
        <linearGradient
          id="cursor-grad0"
          x1="255.428"
          y1="256"
          x2="255.428"
          y2="423"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset=".16" stopColor="#fff" stopOpacity=".39" />
          <stop offset=".658" stopColor="#fff" stopOpacity=".8" />
        </linearGradient>
        <linearGradient
          id="cursor-grad1"
          x1="404.419"
          y1="173.015"
          x2="257.482"
          y2="261.497"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset=".182" stopColor="#fff" stopOpacity=".31" />
          <stop offset=".715" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <linearGradient
          id="cursor-grad2"
          x1="255.428"
          y1="89"
          x2="112.292"
          y2="342.802"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#fff" stopOpacity=".6" />
          <stop offset=".667" stopColor="#fff" stopOpacity=".22" />
        </linearGradient>
        <clipPath id="cursor-clip0">
          <path fill="#fff" d="M0 0h512v512H0z" />
        </clipPath>
        <clipPath id="cursor-clip1">
          <path fill="#fff" transform="translate(85 89)" d="M0 0h343v334H0z" />
        </clipPath>
      </defs>
    </svg>
  );
}

// ============================================
// Lovable AI Icon (Gradient Shape)
// ============================================

function LovableIcon({ className, size = 20 }: { className?: string; size?: number }) {
  return (
    <svg
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 512"
      width={size}
      height={size}
      className={className}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M151.083 0c83.413 0 151.061 67.819 151.061 151.467v57.6h50.283c83.413 0 151.082 67.797 151.082 151.466 0 83.691-67.626 151.467-151.082 151.467H0V151.467C0 67.84 67.627 0 151.083 0z"
        fill="url(#lovable-grad)"
      />
      <defs>
        <radialGradient
          id="lovable-grad"
          cx="0"
          cy="0"
          r="1"
          gradientUnits="userSpaceOnUse"
          gradientTransform="rotate(92.545 118.724 174.844) scale(480.474 650.325)"
        >
          <stop offset=".25" stopColor="#FE7B02" />
          <stop offset=".433" stopColor="#FE4230" />
          <stop offset=".548" stopColor="#FE529A" />
          <stop offset=".654" stopColor="#DD67EE" />
          <stop offset=".95" stopColor="#4B73FF" />
        </radialGradient>
      </defs>
    </svg>
  );
}

// ============================================
// Replit Icon
// ============================================

function ReplitIcon({ className, size = 20 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      className={className}
      fill="currentColor"
    >
      <path d="M2 1.5A1.5 1.5 0 0 1 3.5 0h7A1.5 1.5 0 0 1 12 1.5V8H3.5A1.5 1.5 0 0 1 2 6.5ZM12 8h8.5A1.5 1.5 0 0 1 22 9.5v5a1.5 1.5 0 0 1-1.5 1.5H12ZM2 17.5A1.5 1.5 0 0 1 3.5 16H12v6.5a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 2 22.5Z" />
    </svg>
  );
}

// ============================================
// v0 by Vercel Icon (Text logo style)
// ============================================

function V0Icon({ className, size = 20 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 40 40"
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      className={className}
      fill="currentColor"
    >
      {/* "v" letter */}
      <path d="M6 10L13 30H15L22 10H19L14 25L9 10H6Z" />
      {/* "0" number */}
      <path d="M27 10C23.7 10 21 13.6 21 20C21 26.4 23.7 30 27 30C30.3 30 33 26.4 33 20C33 13.6 30.3 10 27 10ZM27 13C28.7 13 30 15.8 30 20C30 24.2 28.7 27 27 27C25.3 27 24 24.2 24 20C24 15.8 25.3 13 27 13Z" />
    </svg>
  );
}

// ============================================
// Main Platform Icon Component
// ============================================

export function PlatformIcon({ platform, className, size = 20 }: PlatformIconProps) {
  const baseClass = cn("flex-shrink-0", className);

  switch (platform) {
    case "bolt":
      return <BoltIcon className={cn(baseClass, "text-orange-500")} size={size} />;
    case "claude-code":
      return <ClaudeIcon className={baseClass} size={size} />;
    case "cursor":
      return <CursorIcon className={baseClass} size={size} />;
    case "lovable":
      return <LovableIcon className={baseClass} size={size} />;
    case "replit":
      return <ReplitIcon className={cn(baseClass, "text-orange-500")} size={size} />;
    case "v0":
      return <V0Icon className={cn(baseClass, "text-neutral-100")} size={size} />;
    default:
      return <ClaudeIcon className={baseClass} size={size} />;
  }
}

export default PlatformIcon;
