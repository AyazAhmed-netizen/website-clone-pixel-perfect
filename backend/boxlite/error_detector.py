"""
BoxLite Error Detector

Three-layer error detection system:
1. Terminal Detector - Parse terminal output for errors
2. Browser Detector - Use Playwright to detect Vite overlay, React errors, console errors
3. Static Analyzer - Check import paths, basic syntax errors

Usage:
    detector = ErrorDetector(sandbox)
    errors = await detector.detect_all()  # All three layers
    errors = await detector.detect(source="browser")  # Specific layer
"""

import re
import asyncio
import logging
from typing import List, Dict, Any, Optional, Literal
from pathlib import Path

from .models import BuildError, ErrorSource

logger = logging.getLogger(__name__)


# ============================================
# Error Suggestions Mapping
# ============================================

ERROR_SUGGESTIONS = {
    # JSX/Syntax errors
    "Unterminated JSX": "Check for unclosed JSX tags. Every <tag> needs a matching </tag> or self-close with />",
    "Unexpected token": "Check for syntax errors: missing brackets, parentheses, or quotes",
    "Adjacent JSX elements": "Wrap multiple JSX elements in a parent <div> or <> fragment",
    "JSX element": "Check JSX syntax - ensure proper tag structure",

    # Module errors
    "Cannot find module": "Run 'npm install' or check if the package is in package.json",
    "Failed to resolve import": "Check import path - file may not exist or path is incorrect",
    "Module not found": "Verify the module is installed and the import path is correct",
    "is not exported": "Check the export statement in the source file",

    # React errors
    "Invalid hook call": "Hooks can only be called inside function components or custom hooks",
    "is not defined": "Import the variable/component or check for typos in the name",
    "Cannot read property": "Check if the variable is null/undefined before accessing properties",
    "Cannot read properties of undefined": "Add null check or optional chaining (?.) before property access",

    # Type errors
    "TypeError": "Check data types - you may be using a method on wrong type",
    "is not a function": "Check if the variable is actually a function before calling it",

    # Build errors
    "Port .* is already in use": "Stop the other process using the port or use a different port",
    "ENOENT": "File or directory not found - check the path",

    # ============================================
    # Dependency / node_modules errors
    # ============================================
    "ENOENT.*node_modules.*tailwindcss": "Tailwind CSS installation may be corrupted. Try: reinstall_dependencies() or shell('npm install tailwindcss')",
    "ENOENT.*node_modules": "Package files missing. Try: reinstall_dependencies() to clean and reinstall all packages",
    "preflight.css": "Tailwind CSS version mismatch. Try: shell('npm install tailwindcss@^3.4.0') to ensure v3.x",
    "postcss.*ENOENT": "PostCSS configuration issue. Try: reinstall_dependencies() or check postcss.config.js",
    "autoprefixer": "Autoprefixer missing. Try: shell('npm install autoprefixer')",

    # NPM errors
    "npm ERR!": "NPM error occurred. Check error details and try: reinstall_dependencies()",
    "ERESOLVE": "Dependency version conflict. Try: shell('npm install --legacy-peer-deps') or reinstall_dependencies()",
    "peer dep missing": "Missing peer dependency. Install the required package",
    "EINTEGRITY": "Package checksum mismatch. Try: reinstall_dependencies() to clean cache and reinstall",

    # Vite specific
    "vite:css.*ENOENT": "CSS processing error - file not found. Check if the CSS file or dependency exists",
    "Pre-bundling": "Vite pre-bundling issue. Try restarting dev server or reinstall_dependencies()",
}


# Specific error patterns that suggest reinstall_dependencies
REINSTALL_PATTERNS = [
    r"ENOENT.*node_modules",
    r"EINTEGRITY",
    r"npm ERR! code E",
    r"Cannot find module.*node_modules",
    r"preflight\.css",
    r"postcss.*ENOENT",
]


def suggests_reinstall(error_message: str) -> bool:
    """Check if error suggests running reinstall_dependencies"""
    for pattern in REINSTALL_PATTERNS:
        if re.search(pattern, error_message, re.IGNORECASE):
            return True
    return False


def get_suggestion(error_message: str) -> Optional[str]:
    """Generate a fix suggestion based on error message"""
    error_lower = error_message.lower()

    for pattern, suggestion in ERROR_SUGGESTIONS.items():
        if pattern.lower() in error_lower or re.search(pattern, error_message, re.IGNORECASE):
            return suggestion

    return None


# ============================================
# Terminal Detector
# ============================================

class TerminalDetector:
    """Detect errors from terminal output"""

    # Normal log patterns to EXCLUDE (not errors)
    EXCLUDE_PATTERNS = [
        r"\[vite\] hmr update",           # Hot module reload notification
        r"\[vite\] page reload",          # Page reload notification
        r"\[vite\] connected",            # WebSocket connected
        r"\[vite\] ready in",             # Server ready
        r"\[vite\] optimized dependencies", # Dependency optimization
        r"\[vite\] pre-transform",        # Pre-transform notification
        r"\[vite\] ✨",                   # Success messages
        r"VITE v\d+",                     # Version info
        r"ready in \d+ ms",               # Ready timing
        r"Local:.*http",                  # Local URL info
        r"Network:.*http",                # Network URL info
        r"press h \+ enter",              # Help prompt
    ]

    # Error patterns to match
    ERROR_PATTERNS = [
        # Vite/ESBuild errors (highest priority)
        (r"\[plugin:", "Vite Plugin Error"),
        (r"\[vite\].*error", "Vite Error"),  # Only match [vite] with "error"
        (r"\[esbuild\]", "ESBuild Error"),

        # JSX/Babel errors
        (r"Unterminated JSX", "JSX Syntax Error"),
        (r"Unexpected token", "Syntax Error"),
        (r"Adjacent JSX elements", "JSX Error"),
        (r"JSX element", "JSX Error"),

        # Standard errors
        (r"SyntaxError", "Syntax Error"),
        (r"TypeError", "Type Error"),
        (r"ReferenceError", "Reference Error"),

        # Module errors
        (r"Cannot find module", "Module Not Found"),
        (r"Failed to resolve import", "Import Error"),
        (r"Module not found", "Module Not Found"),

        # Build errors
        (r"error:", "Build Error"),
        (r"Error:", "Error"),
        (r"ERROR", "Error"),
        (r"failed to", "Build Failed"),

        # React errors
        (r"Invalid hook call", "React Hook Error"),
        (r"is not defined", "Reference Error"),

        # npm errors
        (r"npm ERR!", "NPM Error"),
        (r"ERESOLVE", "Dependency Resolution Error"),
    ]

    def __init__(self, terminals: Dict[str, Any], dev_server_process: Any = None):
        self.terminals = terminals
        self.dev_server_process = dev_server_process

    def detect(self) -> List[BuildError]:
        """Scan terminal output for errors"""
        errors = []
        seen_messages = set()

        # Collect all terminals to check
        terminals_to_check = list(self.terminals.values())
        if self.dev_server_process and self.dev_server_process not in terminals_to_check:
            terminals_to_check.append(self.dev_server_process)

        for term in terminals_to_check:
            output_buffer = getattr(term, 'output_buffer', [])

            for i, line in enumerate(output_buffer):
                # Skip lines that match exclude patterns (normal logs)
                if any(re.search(p, line, re.IGNORECASE) for p in self.EXCLUDE_PATTERNS):
                    continue

                for pattern, error_type in self.ERROR_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Get context (current line + next few lines)
                        context_lines = output_buffer[i:i+5]
                        full_message = "\n".join(context_lines).strip()

                        # Deduplicate
                        msg_key = full_message[:100]
                        if msg_key in seen_messages:
                            continue
                        seen_messages.add(msg_key)

                        # Extract file path and line number
                        file_path, line_num, col_num = self._extract_location(line, context_lines)

                        errors.append(BuildError(
                            type=error_type,
                            message=full_message[:500],
                            file=file_path,
                            line=line_num,
                            column=col_num,
                            suggestion=get_suggestion(full_message),
                            source=ErrorSource.TERMINAL
                        ))
                        break  # Only match first pattern per line

        return errors

    def _extract_location(self, line: str, context: List[str]) -> tuple:
        """Extract file path, line number, and column from error message"""
        file_path = None
        line_num = None
        col_num = None

        # Combined context for searching
        full_text = "\n".join([line] + context)

        # Pattern 1: /path/file.jsx:108:15
        match = re.search(r'(/[^\s:]+\.(jsx?|tsx?|vue|svelte|css|scss)):(\d+)(?::(\d+))?', full_text)
        if match:
            file_path = match.group(1)
            line_num = int(match.group(3))
            if match.group(4):
                col_num = int(match.group(4))
            return file_path, line_num, col_num

        # Pattern 2: file.jsx:108:15 (without leading /)
        match = re.search(r'([^\s:]+\.(jsx?|tsx?|vue|svelte|css|scss)):(\d+)(?::(\d+))?', full_text)
        if match:
            file_path = match.group(1)
            line_num = int(match.group(3))
            if match.group(4):
                col_num = int(match.group(4))
            return file_path, line_num, col_num

        # Pattern 3: Line 108, Column 15
        match = re.search(r'[Ll]ine[:\s]+(\d+)', full_text)
        if match:
            line_num = int(match.group(1))

        match = re.search(r'[Cc]ol(?:umn)?[:\s]+(\d+)', full_text)
        if match:
            col_num = int(match.group(1))

        # Pattern 4: Just file path
        match = re.search(r'(/[^\s:]+\.(jsx?|tsx?|vue|svelte|css|scss))', full_text)
        if match and not file_path:
            file_path = match.group(1)

        return file_path, line_num, col_num


# ============================================
# Browser Detector (Playwright)
# ============================================

class BrowserDetector:
    """Detect errors from browser preview using Playwright"""

    def __init__(self, preview_url: Optional[str] = None):
        self.preview_url = preview_url
        self._playwright = None
        self._browser = None

    async def detect(self) -> List[BuildError]:
        """Use Playwright to detect browser errors"""
        if not self.preview_url:
            logger.debug("No preview URL, skipping browser detection")
            return []

        errors = []

        try:
            # Try async Playwright first, fall back to sync on Windows Python 3.13
            try:
                await self._detect_browser_async(errors)
            except (NotImplementedError, Exception) as async_err:
                logger.warning(f"[BrowserDetector] Async Playwright failed ({async_err}), trying sync fallback...")
                try:
                    await self._detect_browser_sync(errors)
                except Exception as sync_err:
                    logger.error(f"[BrowserDetector] Sync Playwright also failed: {sync_err}")

        except ImportError:
            logger.warning("Playwright not installed, skipping browser detection")
        except Exception as e:
            logger.error(f"Browser detection failed: {e}")

        return errors

    async def _detect_browser_async(self, errors: List[BuildError]):
        """Async Playwright browser error detection"""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                console_errors = []
                page_errors = []
                page.on('console', lambda msg: console_errors.append(msg) if msg.type == 'error' else None)
                page.on('pageerror', lambda err: page_errors.append(str(err)))

                await page.goto(self.preview_url, timeout=10000, wait_until='domcontentloaded')
                await asyncio.sleep(1)

                vite_errors = await self._detect_vite_overlay(page)
                errors.extend(vite_errors)

                react_errors = await self._detect_react_errors(page)
                errors.extend(react_errors)

                for msg in console_errors:
                    if msg.type == 'error':
                        errors.append(BuildError(
                            type="Console Error",
                            message=msg.text[:500],
                            suggestion=get_suggestion(msg.text),
                            source=ErrorSource.BROWSER
                        ))

                for err in page_errors:
                    errors.append(BuildError(
                        type="Runtime Error",
                        message=err[:500],
                        suggestion=get_suggestion(err),
                        source=ErrorSource.BROWSER
                    ))

            except Exception as e:
                logger.warning(f"Error navigating to preview: {e}")
            finally:
                await browser.close()

    async def _detect_browser_sync(self, errors: List[BuildError]):
        """Sync Playwright browser error detection (fallback for Windows)"""
        import concurrent.futures
        from playwright.sync_api import sync_playwright

        def _sync_detect():
            sync_errors = []
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()

                try:
                    console_errors = []
                    page_errors = []
                    page.on('console', lambda msg: console_errors.append(msg) if msg.type == 'error' else None)
                    page.on('pageerror', lambda err: page_errors.append(str(err)))

                    page.goto(self.preview_url, timeout=10000, wait_until='domcontentloaded')
                    import time
                    time.sleep(1)

                    # Check for Vite error overlay
                    try:
                        overlay = page.query_selector('vite-error-overlay')
                        if overlay:
                            error_info = page.evaluate('''() => {
                                const overlay = document.querySelector('vite-error-overlay');
                                if (!overlay || !overlay.shadowRoot) return null;
                                const root = overlay.shadowRoot;
                                const message = root.querySelector('.message-body')?.textContent || '';
                                const file = root.querySelector('.file')?.textContent || '';
                                const frame = root.querySelector('.frame')?.textContent || '';
                                const tip = root.querySelector('.tip')?.textContent || '';
                                return { message, file, frame, tip };
                            }''')
                            if error_info and error_info.get('message'):
                                sync_errors.append(BuildError(
                                    type="Vite Error",
                                    message=error_info['message'][:500],
                                    frame=error_info.get('frame', ''),
                                    suggestion=error_info.get('tip'),
                                    source=ErrorSource.BROWSER
                                ))
                    except Exception:
                        pass

                    for msg in console_errors:
                        if msg.type == 'error':
                            sync_errors.append(BuildError(
                                type="Console Error",
                                message=msg.text[:500],
                                suggestion=get_suggestion(msg.text),
                                source=ErrorSource.BROWSER
                            ))

                    for err in page_errors:
                        sync_errors.append(BuildError(
                            type="Runtime Error",
                            message=err[:500],
                            suggestion=get_suggestion(err),
                            source=ErrorSource.BROWSER
                        ))

                except Exception as e:
                    logger.warning(f"Error navigating to preview (sync): {e}")
                finally:
                    browser.close()

            return sync_errors

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            sync_errors = await loop.run_in_executor(pool, _sync_detect)
        errors.extend(sync_errors)

    async def _detect_vite_overlay(self, page) -> List[BuildError]:
        """Detect Vite error overlay"""
        errors = []

        try:
            # Vite 4.x uses vite-error-overlay custom element
            overlay = await page.query_selector('vite-error-overlay')

            if overlay:
                # Get shadow root content
                error_info = await page.evaluate('''() => {
                    const overlay = document.querySelector('vite-error-overlay');
                    if (!overlay || !overlay.shadowRoot) return null;

                    const root = overlay.shadowRoot;
                    const message = root.querySelector('.message-body')?.textContent || '';
                    const file = root.querySelector('.file')?.textContent || '';
                    const frame = root.querySelector('.frame')?.textContent || '';
                    const tip = root.querySelector('.tip')?.textContent || '';

                    return { message, file, frame, tip };
                }''')

                if error_info and error_info.get('message'):
                    # Parse file location
                    file_path, line_num, col_num = self._parse_file_location(error_info.get('file', ''))

                    errors.append(BuildError(
                        type="Vite Overlay Error",
                        message=error_info['message'][:500],
                        file=file_path,
                        line=line_num,
                        column=col_num,
                        frame=error_info.get('frame', '')[:300],
                        suggestion=error_info.get('tip') or get_suggestion(error_info['message']),
                        source=ErrorSource.BROWSER
                    ))

            # Also check for Vite 5.x error display
            vite5_error = await page.query_selector('[data-vite-error]')
            if vite5_error:
                content = await vite5_error.text_content()
                if content:
                    errors.append(BuildError(
                        type="Vite Error",
                        message=content[:500],
                        suggestion=get_suggestion(content),
                        source=ErrorSource.BROWSER
                    ))

        except Exception as e:
            logger.debug(f"Vite overlay detection error: {e}")

        return errors

    async def _detect_react_errors(self, page) -> List[BuildError]:
        """Detect React error boundary or error overlay"""
        errors = []

        try:
            # Common React error boundary patterns
            selectors = [
                '[class*="error-boundary"]',
                '[class*="ErrorBoundary"]',
                '#react-error-overlay',
                '[data-react-error]',
                '.react-error-overlay',
            ]

            for selector in selectors:
                element = await page.query_selector(selector)
                if element:
                    content = await element.text_content()
                    if content and len(content) > 10:  # Avoid empty matches
                        # Try to extract stack trace
                        stack = None
                        stack_element = await element.query_selector('pre, code, .stack')
                        if stack_element:
                            stack = await stack_element.text_content()

                        errors.append(BuildError(
                            type="React Error",
                            message=content[:500],
                            stack=stack[:1000] if stack else None,
                            suggestion=get_suggestion(content),
                            source=ErrorSource.BROWSER
                        ))
                        break  # Only report first error boundary

        except Exception as e:
            logger.debug(f"React error detection error: {e}")

        return errors

    def _parse_file_location(self, file_str: str) -> tuple:
        """Parse file:line:column from string"""
        if not file_str:
            return None, None, None

        # Pattern: /path/to/file.jsx:108:15
        match = re.search(r'([^\s:]+):(\d+)(?::(\d+))?', file_str)
        if match:
            return match.group(1), int(match.group(2)), int(match.group(3)) if match.group(3) else None

        return file_str, None, None


# ============================================
# Static Analyzer
# ============================================

class StaticAnalyzer:
    """Static analysis for common errors"""

    def __init__(self, files: Dict[str, str]):
        """
        Args:
            files: Dict of file_path -> content
        """
        self.files = files

    def analyze(self) -> List[BuildError]:
        """Run static analysis on files"""
        errors = []

        for file_path, content in self.files.items():
            # Only analyze JS/JSX/TS/TSX files
            if not file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                continue

            # 1. Check import paths
            import_errors = self._check_imports(file_path, content)
            errors.extend(import_errors)

            # 2. Check basic syntax
            syntax_errors = self._check_basic_syntax(file_path, content)
            errors.extend(syntax_errors)

        return errors

    def _check_imports(self, file_path: str, content: str) -> List[BuildError]:
        """Check if imported files exist"""
        errors = []

        # Find all relative imports
        import_pattern = r'''(?:import\s+.*?\s+from\s+|require\s*\(\s*)['"](\.[^'"]+)['"]'''

        for match in re.finditer(import_pattern, content):
            import_path = match.group(1)
            line_num = content[:match.start()].count('\n') + 1

            # Resolve the import path
            resolved = self._resolve_import(file_path, import_path)

            if resolved and not self._file_exists(resolved):
                errors.append(BuildError(
                    type="Import Error",
                    message=f"Cannot find module '{import_path}'",
                    file=file_path,
                    line=line_num,
                    suggestion=f"Check if file exists at {resolved} or fix the import path",
                    source=ErrorSource.STATIC
                ))

        return errors

    def _check_basic_syntax(self, file_path: str, content: str) -> List[BuildError]:
        """Check for basic syntax issues"""
        errors = []

        # Check for unclosed JSX tags (simple heuristic)
        if file_path.endswith(('.jsx', '.tsx')):
            # Count opening and closing tags (simplified)
            # This is a basic check - not a full parser

            # Check for common JSX issues
            lines = content.split('\n')
            for i, line in enumerate(lines):
                # Check for `<` without proper context
                if '</' in line:
                    # Extract tag name
                    match = re.search(r'</(\w+)', line)
                    if match:
                        closing_tag = match.group(1)
                        # Simple check: is this tag opened somewhere before?
                        preceding = '\n'.join(lines[:i+1])
                        if f'<{closing_tag}' not in preceding and f'<{closing_tag.lower()}' not in preceding.lower():
                            # Could be a closing tag without opening
                            # But this could also be legitimate (component from import)
                            pass  # Skip - too many false positives

        return errors

    def _resolve_import(self, from_file: str, import_path: str) -> Optional[str]:
        """Resolve relative import path to absolute path"""
        if not import_path.startswith('.'):
            return None  # Not a relative import

        from_dir = str(Path(from_file).parent)

        # Handle ./foo and ../foo
        if import_path.startswith('./'):
            resolved = str(Path(from_dir) / import_path[2:])
        elif import_path.startswith('../'):
            resolved = str(Path(from_dir) / import_path)
        else:
            resolved = str(Path(from_dir) / import_path)

        # Normalize path
        resolved = str(Path(resolved).resolve()) if not resolved.startswith('/') else resolved

        return resolved

    def _file_exists(self, path: str) -> bool:
        """Check if file exists in our file system"""
        # Check exact path
        if path in self.files:
            return True

        # Check with common extensions
        extensions = ['', '.js', '.jsx', '.ts', '.tsx', '/index.js', '/index.jsx', '/index.ts', '/index.tsx']
        for ext in extensions:
            if (path + ext) in self.files:
                return True

        return False


# ============================================
# Main Error Detector
# ============================================

class ErrorDetector:
    """
    Unified error detection system.

    Combines three detection layers:
    - Terminal: Parse terminal output
    - Browser: Playwright-based detection
    - Static: Static code analysis
    """

    def __init__(self, sandbox):
        """
        Args:
            sandbox: BoxLiteSandboxManager instance
        """
        self.sandbox = sandbox

    async def detect(
        self,
        source: Literal["all", "terminal", "browser", "static"] = "all"
    ) -> List[BuildError]:
        """
        Detect errors from specified source(s).

        Args:
            source: Which layer(s) to check
                - "all": All three layers (parallel)
                - "terminal": Only terminal output
                - "browser": Only Playwright browser check
                - "static": Only static analysis

        Returns:
            List of BuildError objects
        """
        if source == "terminal":
            return self._detect_terminal()
        elif source == "browser":
            return await self._detect_browser()
        elif source == "static":
            return self._detect_static()
        else:
            # Run all three in parallel
            return await self.detect_all()

    async def detect_all(self) -> List[BuildError]:
        """Run all three detectors in parallel and merge results"""
        # Terminal and static are sync, browser is async
        terminal_errors = self._detect_terminal()
        static_errors = self._detect_static()
        browser_errors = await self._detect_browser()

        # Merge and deduplicate
        all_errors = terminal_errors + browser_errors + static_errors
        return self._deduplicate(all_errors)

    async def quick_check(self) -> List[BuildError]:
        """
        Quick error check (for auto-attach to write_file etc.)
        Only runs terminal + static (no Playwright - too slow)
        """
        terminal_errors = self._detect_terminal()
        static_errors = self._detect_static()
        return self._deduplicate(terminal_errors + static_errors)

    def _detect_terminal(self) -> List[BuildError]:
        """Run terminal detector"""
        detector = TerminalDetector(
            terminals=self.sandbox.terminals,
            dev_server_process=getattr(self.sandbox, 'dev_server_process', None)
        )
        return detector.detect()

    async def _detect_browser(self) -> List[BuildError]:
        """Run browser detector"""
        preview_url = self.sandbox.state.preview_url
        detector = BrowserDetector(preview_url=preview_url)
        return await detector.detect()

    def _detect_static(self) -> List[BuildError]:
        """Run static analyzer"""
        analyzer = StaticAnalyzer(files=self.sandbox.state.files)
        return analyzer.analyze()

    def _deduplicate(self, errors: List[BuildError]) -> List[BuildError]:
        """Remove duplicate errors"""
        seen = set()
        unique = []

        for error in errors:
            # Create a key for deduplication
            key = (
                error.file,
                error.line,
                error.message[:50] if error.message else ""
            )

            if key not in seen:
                seen.add(key)
                unique.append(error)

        # Sort by source priority: browser > terminal > static
        priority = {
            ErrorSource.BROWSER: 0,
            ErrorSource.TERMINAL: 1,
            ErrorSource.STATIC: 2,
        }
        unique.sort(key=lambda e: (priority.get(e.source, 99), e.file or "", e.line or 0))

        return unique
