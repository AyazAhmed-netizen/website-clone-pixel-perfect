/**
 * Prompt Templates for AI Code Platforms
 *
 * Platform-specific templates for exporting code with context
 * to various AI development tools.
 */

import type { ExportableFile } from "./code-export-utils";
import { generateFileTree } from "./code-export-utils";

// ============================================
// Types
// ============================================

export type PlatformType =
  | "bolt"
  | "claude-code"
  | "cursor"
  | "lovable"
  | "replit"
  | "v0";

export interface PlatformInfo {
  id: PlatformType;
  name: string;
  icon: string; // Icon identifier
  description: string;
}

export interface PromptGeneratorOptions {
  files: ExportableFile[];
  platform: PlatformType;
  additionalContext?: string;
  projectName?: string;
}

// ============================================
// Platform Definitions
// ============================================

export const PLATFORMS: PlatformInfo[] = [
  {
    id: "bolt",
    name: "Bolt.new",
    icon: "bolt",
    description: "Optimized for Bolt.new",
  },
  {
    id: "claude-code",
    name: "Claude Code",
    icon: "claude",
    description: "Optimized for Claude Code",
  },
  {
    id: "cursor",
    name: "Cursor (or any AI IDE)",
    icon: "cursor",
    description: "Optimized for Cursor and similar AI IDEs",
  },
  {
    id: "lovable",
    name: "Lovable",
    icon: "lovable",
    description: "Optimized for Lovable",
  },
  {
    id: "replit",
    name: "Replit",
    icon: "replit",
    description: "Optimized for Replit Agent",
  },
  {
    id: "v0",
    name: "v0 by Vercel",
    icon: "v0",
    description: "Optimized for v0 by Vercel",
  },
];

// ============================================
// Template Generators
// ============================================

/**
 * Generate file content block for prompt
 */
function generateFileBlocks(files: ExportableFile[]): string {
  return files
    .map((file) => {
      const ext = file.path.split(".").pop() || "";
      const language = getLanguageFromExtension(ext);
      return `### ${file.path}

\`\`\`${language}
${file.content}
\`\`\``;
    })
    .join("\n\n");
}

/**
 * Get language identifier from file extension
 */
function getLanguageFromExtension(ext: string): string {
  const map: Record<string, string> = {
    js: "javascript",
    jsx: "jsx",
    ts: "typescript",
    tsx: "tsx",
    css: "css",
    scss: "scss",
    html: "html",
    json: "json",
    md: "markdown",
    vue: "vue",
    svelte: "svelte",
  };
  return map[ext.toLowerCase()] || ext;
}

/**
 * Generate prompt for Bolt.new
 */
function generateBoltPrompt(options: PromptGeneratorOptions): string {
  const { files, additionalContext, projectName = "Project" } = options;
  const fileTree = generateFileTree(files);
  const fileBlocks = generateFileBlocks(files);

  return `# ${projectName}

I have an existing codebase that I'd like you to work with. Please review the code structure and files below.

## Project Structure

\`\`\`
${fileTree}
\`\`\`

## Files

${fileBlocks}

${additionalContext ? `## Additional Context\n\n${additionalContext}\n` : ""}
## Instructions

Please review this codebase and help me continue development. The project uses:
- React with JSX/TSX
- Tailwind CSS for styling
- Vite as the build tool

You can modify existing files or create new ones as needed.`;
}

/**
 * Generate prompt for Claude Code
 */
function generateClaudeCodePrompt(options: PromptGeneratorOptions): string {
  const { files, additionalContext, projectName = "Project" } = options;
  const fileTree = generateFileTree(files);
  const fileBlocks = generateFileBlocks(files);

  return `# ${projectName} - Code Import

Please import and work with this codebase. Here's the complete project structure and files.

## File Structure

\`\`\`
${fileTree}
\`\`\`

## Source Files

${fileBlocks}

${additionalContext ? `## Context\n\n${additionalContext}\n` : ""}
## Setup Instructions

1. Create these files in your project directory
2. Run \`npm install\` to install dependencies
3. Run \`npm run dev\` to start the development server

The project is set up with:
- React 18
- Tailwind CSS
- Vite

Feel free to modify and improve the code as needed.`;
}

/**
 * Generate prompt for Cursor
 */
function generateCursorPrompt(options: PromptGeneratorOptions): string {
  const { files, additionalContext, projectName = "Project" } = options;
  const fileTree = generateFileTree(files);
  const fileBlocks = generateFileBlocks(files);

  return `# ${projectName}

## Overview

This is an existing React + Tailwind CSS project that needs to be set up in your IDE.

## Project Structure

\`\`\`
${fileTree}
\`\`\`

## File Contents

${fileBlocks}

${additionalContext ? `## Additional Notes\n\n${additionalContext}\n` : ""}
## Development Setup

\`\`\`bash
# Install dependencies
npm install

# Start development server
npm run dev
\`\`\`

## Tech Stack

- React 18 with JSX
- Tailwind CSS for styling
- Vite for build tooling

Please help me create these files and continue development.`;
}

/**
 * Generate prompt for Lovable
 */
function generateLovablePrompt(options: PromptGeneratorOptions): string {
  const { files, additionalContext, projectName = "Project" } = options;
  const fileTree = generateFileTree(files);
  const fileBlocks = generateFileBlocks(files);

  return `# Import: ${projectName}

I want to import this existing codebase into Lovable.

## Structure

\`\`\`
${fileTree}
\`\`\`

## Code

${fileBlocks}

${additionalContext ? `## Notes\n\n${additionalContext}\n` : ""}
## Stack

- React + Tailwind CSS
- Vite build system

Please recreate this project and help me continue building it.`;
}

/**
 * Generate prompt for Replit
 */
function generateReplitPrompt(options: PromptGeneratorOptions): string {
  const { files, additionalContext, projectName = "Project" } = options;
  const fileTree = generateFileTree(files);
  const fileBlocks = generateFileBlocks(files);

  return `# ${projectName} - Replit Import

Create a new React + Vite project with the following structure and files.

## File Tree

\`\`\`
${fileTree}
\`\`\`

## Files

${fileBlocks}

${additionalContext ? `## Context\n\n${additionalContext}\n` : ""}
## Configuration

This project uses:
- React 18
- Tailwind CSS
- Vite

After creating the files, run:
1. \`npm install\`
2. \`npm run dev\`

The dev server should start on the default port.`;
}

/**
 * Generate prompt for v0 by Vercel
 */
function generateV0Prompt(options: PromptGeneratorOptions): string {
  const { files, additionalContext, projectName = "Project" } = options;
  const fileTree = generateFileTree(files);
  const fileBlocks = generateFileBlocks(files);

  return `# ${projectName}

## Project Files

\`\`\`
${fileTree}
\`\`\`

## Source Code

${fileBlocks}

${additionalContext ? `## Additional Requirements\n\n${additionalContext}\n` : ""}
## Tech Stack

- React with Tailwind CSS
- Component-based architecture

Please help me recreate and enhance these components.`;
}

// ============================================
// Main Generator
// ============================================

/**
 * Generate prompt for specified platform
 */
export function generatePrompt(options: PromptGeneratorOptions): string {
  const { platform } = options;

  switch (platform) {
    case "bolt":
      return generateBoltPrompt(options);
    case "claude-code":
      return generateClaudeCodePrompt(options);
    case "cursor":
      return generateCursorPrompt(options);
    case "lovable":
      return generateLovablePrompt(options);
    case "replit":
      return generateReplitPrompt(options);
    case "v0":
      return generateV0Prompt(options);
    default:
      return generateCursorPrompt(options); // Default to generic format
  }
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (error) {
    console.error("Failed to copy to clipboard:", error);
    // Fallback for older browsers
    try {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      return true;
    } catch {
      return false;
    }
  }
}
