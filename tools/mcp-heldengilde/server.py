#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp==1.28.1"]
# ///
"""
Heldengilde MCP server for Claude Code / Cursor.
Searches the TTRPG source docs, lists server-owned NPCs and dungeons, validates
the content YAML and triggers a deploy of the pushed content repo.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Heldengilde-Minecraft-TTRPG")

CONTENT_ROOT = Path(os.environ.get("HG_CONTENT_ROOT", ".")).resolve()
INFRA_ROOT = Path(os.environ.get("HG_INFRA_ROOT", CONTENT_ROOT.parent / "heldengilde-minecraft-infra")).resolve()
TTRPG_DOCS_DIR = CONTENT_ROOT / "docs" / "ttrpg-source"
SOURCE_SUFFIXES = {".md", ".txt", ".yml", ".yaml", ".json"}
CRUCIBLE_TRIGGERS = re.compile(r"~on(Use|Swing|Crouch)\b")


@mcp.tool()
def search_ttrpg_rules_and_lore(query: str) -> str:
    """
    Search the Heldengilde TTRPG rulebooks, classes, spells and lore in
    docs/ttrpg-source/ (case-insensitive). Call this before generating quests, items or skills.
    """
    if not TTRPG_DOCS_DIR.exists():
        return "TTRPG source directory (docs/ttrpg-source/) does not exist yet."

    matches = []
    q_lower = query.lower()
    for path in sorted(TTRPG_DOCS_DIR.rglob("*")):
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for idx, line in enumerate(lines, start=1):
            if q_lower in line.lower():
                snippet = "\n".join(lines[max(0, idx - 3): idx + 5])
                matches.append(f"--- {path.relative_to(CONTENT_ROOT)}:{idx} ---\n{snippet}")
                if len(matches) >= 15:
                    return "\n\n".join(matches)
    return "\n\n".join(matches) if matches else f"No matches found for '{query}'."


@mcp.tool()
def list_ingame_npcs_and_dungeons() -> str:
    """
    Inspect the server-owned snapshots (Citizens saves.yml, MythicDungeons maps and loot tables)
    so generated BetonQuest packages bind to real NPC IDs and dungeon names. Read-only.
    """
    owned = CONTENT_ROOT / "server-owned"
    citizens_file = owned / "Citizens" / "saves.yml"
    maps_dir = owned / "MythicDungeons" / "maps"
    loot_dir = owned / "MythicDungeons" / "loottables"

    report = ["=== Citizens NPCs (server-owned/Citizens/saves.yml) ==="]
    if citizens_file.exists():
        for line in citizens_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if re.match(r"^'?\d+'?:$", stripped) or stripped.startswith(("name:", "uuid:")):
                report.append(line)
    else:
        report.append("No Citizens saves.yml snapshot found yet.")

    report.append("\n=== MythicDungeons maps ===")
    if maps_dir.exists() and any(maps_dir.iterdir()):
        for d in sorted(p for p in maps_dir.iterdir() if p.is_dir()):
            files = ", ".join(sorted(f.name for f in d.glob("*.yml"))) or "no yml files"
            report.append(f"- Dungeon: {d.name} ({files})")
    else:
        report.append("No MythicDungeons snapshots found yet.")

    report.append("\n=== MythicDungeons loot tables ===")
    tables = sorted(loot_dir.glob("*.yml")) if loot_dir.exists() else []
    report.extend(f"- {t.stem}" for t in tables) if tables else report.append("None yet.")
    return "\n".join(report)


@mcp.tool()
def validate_content() -> str:
    """
    Run yamllint on BetonQuest/ and MythicMobs/ and flag MythicCrucible-only triggers
    (~onUse, ~onSwing, ~onCrouch) in MythicMobs/Items/ (not allowed, see ADR 0008).
    """
    report = []
    targets = [str(CONTENT_ROOT / d) for d in ("BetonQuest", "MythicMobs")]
    if shutil.which("yamllint"):
        res = subprocess.run(["yamllint", "-c", str(CONTENT_ROOT / ".yamllint"), *targets],
                             capture_output=True, text=True, check=False)
        report.append(f"yamllint exit={res.returncode}\n{res.stdout}{res.stderr}".strip())
    else:
        report.append("yamllint not found on PATH; install it (pipx install yamllint).")

    hits = []
    items_dir = CONTENT_ROOT / "MythicMobs" / "Items"
    for path in sorted(items_dir.rglob("*.yml")) if items_dir.exists() else []:
        for idx, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            if CRUCIBLE_TRIGGERS.search(line):
                hits.append(f"{path.relative_to(CONTENT_ROOT)}:{idx}: Crucible trigger: {line.strip()}")
    report.append("Crucible triggers: " + ("\n" + "\n".join(hits) if hits else "none"))
    return "\n".join(report)


@mcp.tool()
def live_reload_and_verify() -> str:
    """
    Run `hg-gitops.sh deploy-content` from the infra checkout. This deploys the PUSHED main branch
    of the content repo, not the working tree: commit and push first. Reloads BetonQuest and
    MythicMobs on the server. If HG_SERVER_LOG is set, also returns recent WARN/ERROR lines
    mentioning them.
    """
    agent = INFRA_ROOT / "agent" / "hg-gitops.sh"
    if not agent.exists():
        return f"{agent} not found; set HG_INFRA_ROOT, or run validate_content and the CI boot-test instead."
    res = subprocess.run(["bash", str(agent), "deploy-content"], capture_output=True, text=True, check=False)
    out = f"Deploy exit={res.returncode}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    log = os.environ.get("HG_SERVER_LOG")
    if log and Path(log).exists():
        lines = Path(log).read_text(encoding="utf-8", errors="ignore").splitlines()[-2000:]
        problems = [l for l in lines if re.search(r"(WARN|ERROR)", l) and re.search(r"BetonQuest|MythicMobs", l)]
        out += "\nRecent problems:\n" + ("\n".join(problems[-30:]) or "none")
    return out


if __name__ == "__main__":
    mcp.run()
