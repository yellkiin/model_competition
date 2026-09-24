#!/usr/bin/env python3
"""Academic Figure Skill Cross-Platform Adapter Generator.

Reads academic-figure-skill/SKILL.md and generates platform-specific adapter files for:
  - Claude Code    (already supported via ~/.claude/skills/)
  - OpenAI Codex   (manifest.yaml)
  - Cursor         (.cursorrules)
  - GitHub Copilot (copilot-instructions.md)

Usage:
    python generate_adapters.py                    # generate all, output to install/
    python generate_adapters.py --target cursor    # generate cursor only
    python generate_adapters.py --target copilot   # generate copilot only
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = PROJECT_ROOT / "academic-figure-skill" / "SKILL.md"
INSTALL_DIR = SKILL_MD.parent / "install"

# ═══════════════════════════════════════════════════════════
# Core rule extractor — pulls the 50-line essence from SKILL.md
# ═══════════════════════════════════════════════════════════

def extract_core_rules() -> str:
    """Portable pointer to the authoritative workflow, with no competing style block."""
    if not SKILL_MD.is_file(): raise FileNotFoundError(SKILL_MD)
    return """# Academic Figure Skill portable workflow
Read SKILL.md and references/asset-reference-protocol.md from this installed skill.
For Huawei Cup, Codex uses .agents/skills/academic-figure-skill and Claude Code uses .claude/skills/academic-figure-skill. Pass the matching --runtime explicitly to project tools. Never silently use the other mirror.
Huawei Cup ordinary figures compare academic-figure-skill and modelviz-skill as equal sources under the project drawing specification. The academic asset/source evidence below applies only to panels selected from academic; modelviz panels retain their own audited template and adaptation evidence. Flowcharts retain scibox-diagram/draw.io and mechanisms retain their applicable project chain.
Understand real data before choosing chart or layout. Actually view the complete gallery overview once per project/asset version, then inspect per-figure candidate originals and all relevant family scripts/outputs. Initializers must not fill review conclusions.
Record five-way mapping, candidate decisions and concrete style inheritance. Priority: science and real data semantics, Chinese and actual paper readability, selected reference design, generic defaults. Do not inject fixed palette, spine removal, journal width or asymmetric layout.
Copy the selected source, adapt real inputs and justified display parameters, genuinely execute, and export vector plus PNG. Use chinese_fonts.py and actual font smoke viewing. Null effects/constant data must stay unchanged.
Actually open reference/current comparison, PNG, rendered PDF, grayscale and actual paper page. Report science, design inheritance and print readability separately. Run plan/render/paper project gates; static checks and hashes do not prove beauty or cognition.
Automatic paper mode makes routine evidence-backed choices without per-figure confirmation. Missing necessary inputs, units, runtime or permissions require the smallest actual clarification.
"""


def _extract_code_block(path: Path, language: str) -> str:
    """Extract the first fenced code block for the given language from a markdown file."""
    if not path.exists():
        return f"# {language} block not found"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Match ```language ... ```  (language can be python or r)
    pattern = rf"```\s*{language}\s*\n(.*?)```"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return f"# No {language} block found in {path.name}"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ═══════════════════════════════════════════════════════════
# Platform generators
# ═══════════════════════════════════════════════════════════

def generate_claude_code(core: str) -> str:
    return "# Claude Code project adapter\n\nUse the project .claude/skills/academic-figure-skill/SKILL.md and root CLAUDE.md. Pass --runtime claude to project tools. Keep shared skill sources identical to the Codex mirror.\n\n" + core



def generate_codex_manifest(core: str):
    # Retained as bundle metadata for existing distributions, not a required Codex API.
    manifest = 'name: academic-figure-skill\nversion: "2.0.0"\nentrypoint: SKILL.md\ndescription: Asset-based Huawei Cup scientific figure workflow\n'
    instructions = '# Codex project adapter\n\nRead .agents/skills/academic-figure-skill/SKILL.md and root AGENTS.md; pass --runtime codex. manifest.yaml is compatibility bundle metadata, not a substitute for SKILL.md.\n\n' + core
    return manifest, instructions



def generate_cursor_rules(core: str) -> str:
    return '# Academic figure project adapter\n\n' + core



def generate_copilot_instructions(core: str) -> str:
    """GitHub Copilot: inject as .github/copilot-instructions.md."""
    return f'''# Academic Figure Skill — Scientific Figure Instructions for GitHub Copilot
# Place this file at: <your-repo>/.github/copilot-instructions.md
# Generated: {_now()}

{core}
'''


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

TARGETS = {
    "claude-code": "Claude Code (README)",
    "codex": "OpenAI Codex (manifest + instructions)",
    "cursor": "Cursor (.cursorrules)",
    "copilot": "GitHub Copilot (copilot-instructions.md)",
}


def generate(target: str | None = None):
    """Generate adapters. If target is None, generate all."""
    core = extract_core_rules()

    targets_to_build = [target] if target else list(TARGETS)
    for t in targets_to_build:
        if t not in TARGETS:
            print(f"Unknown target: {t}. Choose from: {', '.join(TARGETS)}")
            sys.exit(1)

    print(f"Academic Figure Skill Adapter Generator — {_now()}")
    print(f"Source: {SKILL_MD}")
    print()

    for t in targets_to_build:
        out_dir = INSTALL_DIR / t
        out_dir.mkdir(parents=True, exist_ok=True)

        if t == "claude-code":
            readme = generate_claude_code(core)
            path = out_dir / "README.md"
            path.write_text(readme, encoding="utf-8")
            print(f"[OK] {t} → {path}")

        elif t == "codex":
            manifest, instructions = generate_codex_manifest(core)
            (out_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")
            (out_dir / "instructions.md").write_text(instructions, encoding="utf-8")
            print(f"[OK] {t} → {out_dir}/manifest.yaml + instructions.md")

        elif t == "cursor":
            rules = generate_cursor_rules(core)
            path = out_dir / ".cursorrules"
            path.write_text(rules, encoding="utf-8")
            print(f"[OK] {t} → {path}")

        elif t == "copilot":
            instructions = generate_copilot_instructions(core)
            path = out_dir / "copilot-instructions.md"
            path.write_text(instructions, encoding="utf-8")
            print(f"[OK] {t} → {path}")

    print(f"\nAll generated under: {INSTALL_DIR}")
    print("Copy the relevant file(s) to your project/agent directory.")


if __name__ == "__main__":
    target = None
    if "--target" in sys.argv:
        idx = sys.argv.index("--target")
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]
    generate(target)
