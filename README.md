# heldengilde-minecraft-content

Game content for the Heldengilde Minecraft server (Paper 26.2). Infrastructure lives in `heldengilde-minecraft-infra`; ownership rules are in its ADR 0003.

| Path | Owner | Goes to |
|---|---|---|
| `BetonQuest/QuestPackages/` | Git (PR-reviewed) | `plugins/BetonQuest/QuestPackages/` |
| `MythicMobs/{Mobs,Skills,Items}/` | Git (PR-reviewed) | `plugins/MythicMobs/{Mobs,Skills,Items}/` |
| `server-owned/` | Server (auto-PR from branch `autosync/server`) | read-only here |
| `docs/ttrpg-source/` | Git | input for the AI tools |

`hg-gitops deploy-content` on the host pulls `main`, mirrors the Git-owned directories with `rsync --delete`, then runs `bq reload` and `mm reload`.

## AI tooling

`CLAUDE.md` is the standing instruction set. `.mcp.json` registers the `heldengilde-ttrpg` MCP server (`tools/mcp-heldengilde/server.py`, run with `uv`). Environment: `HG_CONTENT_ROOT` (default `.`), `HG_INFRA_ROOT` (default `../heldengilde-minecraft-infra`), `HG_AGENT_ENV` and `HG_SERVER_LOG` (optional).

## Checks

`yamllint .` and `pre-commit run -a`. CI only validates; it never deploys.
