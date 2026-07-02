"""
Prompt templates extracted and adapted from the screenshot-to-code project.

These templates guide the LLM in converting screenshots to code with
maximal fidelity to the original design.
"""

from dataclasses import dataclass, field
from typing import Literal

StackType = Literal[
    "html_tailwind",
    "html_css",
    "react_tailwind",
    "vue_tailwind",
    "bootstrap",
    "ionic_tailwind",
]


@dataclass
class StackConfig:
    """Configuration for a supported technology stack."""

    name: str
    key: StackType
    description: str
    scripts: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


STACKS: dict[StackType, StackConfig] = {
    "html_tailwind": StackConfig(
        name="HTML + Tailwind CSS",
        key="html_tailwind",
        description="Modern utility-first CSS framework — best for most designs.",
        scripts=['<script src="https://cdn.tailwindcss.com"></script>'],
    ),
    "html_css": StackConfig(
        name="HTML + CSS",
        key="html_css",
        description="Pure HTML, CSS, and vanilla JavaScript. No frameworks.",
        notes=[
            "Do NOT use Tailwind or any CSS framework.",
            "Define all styles inline in a <style> block.",
        ],
    ),
    "react_tailwind": StackConfig(
        name="React + Tailwind CSS",
        key="react_tailwind",
        description="React 18 with Babel standalone for in-browser JSX + Tailwind.",
        scripts=[
            '<script src="https://cdn.jsdelivr.net/npm/react@18.0.0/umd/react.development.js"></script>',
            '<script src="https://cdn.jsdelivr.net/npm/react-dom@18.0.0/umd/react-dom.development.js"></script>',
            '<script src="https://unpkg.com/@babel/standalone@7.25.6/babel.min.js"></script>',
            '<script src="https://cdn.tailwindcss.com"></script>',
        ],
        notes=[
            "Use <script type=\"text/babel\"> for JSX code blocks.",
            "Mount with ReactDOM.createRoot(document.getElementById('root')).render(...)",
            "IMPORTANT: Pin Babel to 7.25.6 — Babel 8's automatic JSX runtime injects 'import' which breaks in-browser transforms.",
        ],
    ),
    "vue_tailwind": StackConfig(
        name="Vue 3 + Tailwind CSS",
        key="vue_tailwind",
        description="Vue 3.3 global build + Tailwind CSS.",
        scripts=[
            '<script src="https://registry.npmmirror.com/vue/3.3.11/files/dist/vue.global.js"></script>',
            '<script src="https://cdn.tailwindcss.com"></script>',
        ],
        notes=[
            "Use Vue with the global build: const { createApp, ref } = Vue",
            "Mount with createApp({...}).mount('#app')",
        ],
    ),
    "bootstrap": StackConfig(
        name="Bootstrap 5",
        key="bootstrap",
        description="Bootstrap 5.3 — component-based framework.",
        styles=[
            '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-T3c6CoIi6uLrA9TneNEoa7RxnatzjcDSCmG1MXxSR1GAsXEV/Dwwykc2MPK8M2HN" crossorigin="anonymous">',
        ],
        scripts=[
            '<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js" integrity="sha384-C6RzsynM9kWDrMNeT87bh95OGNyZPhcTNXj1NW7RuBCsyN/o0jlpcV8Qyq46cDfL" crossorigin="anonymous"></script>',
        ],
    ),
    "ionic_tailwind": StackConfig(
        name="Ionic + Tailwind CSS",
        key="ionic_tailwind",
        description="Ionic Framework components + Tailwind for mobile-first UIs.",
        scripts=[
            '<script type="module" src="https://cdn.jsdelivr.net/npm/@ionic/core/dist/ionic/ionic.esm.js"></script>',
            '<script nomodule src="https://cdn.jsdelivr.net/npm/@ionic/core/dist/ionic/ionic.js"></script>',
            '<script src="https://cdn.tailwindcss.com"></script>',
        ],
        styles=[
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@ionic/core/css/ionic.bundle.css" />',
        ],
        notes=[
            "For ionicons, add near </body>:",
            '<script type="module">import ionicons from "https://cdn.jsdelivr.net/npm/ionicons/+esm"</script>',
            '<script nomodule src="https://cdn.jsdelivr.net/npm/ionicons/dist/esm/ionicons.min.js"></script>',
        ],
    ),
}


def build_stack_prompt(stack_key: StackType) -> str:
    """Generate the stack-specific portion of the user prompt."""
    config = STACKS[stack_key]
    parts = [f"## Technology Stack: {config.name}", config.description, ""]

    if config.scripts:
        parts.append("Include these script tags:")
        for s in config.scripts:
            parts.append(f"  {s}")
        parts.append("")

    if config.styles:
        parts.append("Include these style/link tags:")
        for s in config.styles:
            parts.append(f"  {s}")
        parts.append("")

    if config.notes:
        parts.append("Special instructions:")
        for note in config.notes:
            parts.append(f"  - {note}")
        parts.append("")

    return "\n".join(parts)


# ---- System Prompt (adapted from backend/prompts/system_prompt.py) ----

SYSTEM_PROMPT = """
You are an expert frontend developer who converts UI screenshots into clean, pixel-perfect code.

# Rules

- Be extremely concise in your chat responses.
- Do NOT include code snippets in your messages. Use the file creation tool for all code.
- Generate a single, self-contained HTML file at path "index.html".
- The file must be standalone: all CSS and JS inline, all dependencies from CDN.
- At the end of the task, respond with a one or two sentence summary of what was built.
- Always respond to the user in the language they used.

# Quality Standards

- The page must look EXACTLY like the screenshot.
- Use the exact text from the screenshot. Do not paraphrase or summarize.
- Match colors precisely: backgrounds, text, accents, borders, dividers.
- Match font sizes, font weights, line heights, and letter spacing.
- Match padding, margins, and gaps between elements.
- Match border styles, border-radius values, and box-shadow effects.
- Use the exact images from the screenshot where possible; otherwise note what needs replacing.

# Icons & Fonts

- For icons, use Font Awesome 5 (CDN): <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
- For Ionic stacks, use ionicons instead.
- For fonts, use Google Fonts. If the exact font is unknown, pick the closest match.
""".strip()


# ---- User Prompt (adapted from backend/prompts/create/image.py) ----

def build_image_prompt(
    stack_key: StackType,
    text_prompt: str = "",
) -> str:
    """
    Build the user prompt for a screenshot-to-code generation.

    Args:
        stack_key: The target technology stack.
        text_prompt: Additional instructions from the user (e.g., "make the button blue").
    """
    stack_section = build_stack_prompt(stack_key)

    prompt = f"""
Generate code for a web page that looks exactly like the provided screenshot(s).

{stack_section}

## Replication Instructions

- Make sure the web page looks EXACTLY like the screenshot.
- Pay extreme attention to detail: colors, spacing, fonts, sizes, and layout.
- Use the exact text content from the screenshot.
- If a text appears to be a specific font size/weight, match it.
- For images in the screenshot, use descriptive alt text and a placeholder image or SVG placeholder.
- Replicate gradients, shadows, and border-radius exactly as seen.
- For icons, find the closest Font Awesome icon.

## If Multiple Screenshots

- Different pages → create separate sections with navigation links between them.
- Different tabs/views → build tab navigation or a view switcher.
- Unrelated screenshots → label them "Screenshot 1", "Screenshot 2", etc.
- For mobile screenshots, ignore device frames; focus on the UI content only.
""".strip()

    if text_prompt.strip():
        prompt += f"\n\n## Additional Instructions\n{text_prompt.strip()}"

    return prompt


# ---- Self-Review Prompt (for the verification phase) ----

SELF_REVIEW_PROMPT = """
Review the code you just generated against the original screenshot.

Check the following and fix any discrepancies:
1. Colors: backgrounds, text, accents, borders — exact match required
2. Typography: font family, sizes, weights, line heights
3. Spacing: padding, margins, gaps between elements
4. Layout: section order, column structure, alignment
5. Content: all text present and correct, images described
6. Details: border-radius, shadows, dividers, button styles

If you identify issues, use edit_file to fix them immediately.
""".strip()
