# Install delegate-to-opencode skill and make it work on opencode v2.2.7

## Task
Install https://github.com/luckeyfaraday/delegate-to-opencode as a Claude Code skill so Claude can use
opencode as a background sub-agent.

## Repo
- Upstream: https://github.com/luckeyfaraday/delegate-to-opencode (read-only, nothing pushed; remote `upstream`)
- Fork (public, same visibility as upstream): https://github.com/mufidhadi/delegate-to-opencode (remote `origin`, ssh)
- Pushed branch `fix/opencode-v2-compat` only; fork `main` is untouched upstream `main`
- Local clone: `~/project/mufid/delegate-to-opencode`
- Install: symlink `~/.claude/skills/opencode -> ~/project/mufid/delegate-to-opencode`
- Branch: `fix/opencode-v2-compat`
- Commit: `0f80559` (base upstream `fc25aaa`)

## Tech stack
bash + jq (wrapper), opencode v2.2.7 CLI, pytest 9.2 via uv (tests).

## Action history
1. Researched options (web) and probed `opencode run --format json` on this machine.
2. Cloned upstream into a new directory and read every file (script 105 lines: no network calls, no eval).
3. Symlinked into `~/.claude/skills/opencode`; `--help` worked.
4. Real run failed: `Unrecognized flag: --dir in command opencode run`.
5. Branch `fix/opencode-v2-compat`; wrote pytest suite first (9 red / 1 green), then fixed the script (10 green).
6. Verified against real opencode: PONG run, variant error surfaced, real file edit confirmed by `git diff`.
7. Updated SKILL.md notes (variant syntax, explicit `-m` on this laptop).

## Difficulties, bugs, solutions
| Problem | Evidence | Solution |
|---|---|---|
| `--dir` not supported by v2 | `Unrecognized flag: --dir` | run in subshell: `( cd "$WORKDIR" && opencode ... )` |
| `--variant` not supported by v2 | `opencode run --help` shows `--model provider/model#variant` only | `-v` appends `#variant` to model; `-v` without `-m` exits 2 |
| `last_message.txt` always empty | real event: `{"type":"text","part":{"text":"PONG"}}` | jq reads `.part.text // .text // .data` |
| `meta.json` never written on success | v2 ends with `step_finish`, not `end`/`done` | include `step_finish` |
| Provider errors hidden | error event only in events.jsonl | wrapper prints `opencode error: <message>` from `error.txt` |
| opencode default model fails here | `provider.invalid-request` (OpenRouter allowed-providers) | always pass `-m`; documented in SKILL.md |
| Other providers unusable now | `deepseek/*` 402 Insufficient Balance; `opencode/*-free` 429 free limit | use `opencode-go/*` (qwen3.8-flash worked) |
| `uv init` edited parent workspace `~/project/mufid/pyproject.toml` and `uv.lock` | uv printed "Adding ... as member of workspace" | removed my member entry, re-init with `--no-workspace`, re-ran `uv lock` in parent (55 packages, 0 mentions of delegate-to-opencode). Parent files are untracked, so the revert is not diff-verifiable; it was checked by reading the file and lock. |

## Tests and results
- `uv run pytest tests -q` before fix: 9 failed, 1 passed. After fix: **10 passed**.
- Real: `run-opencode.sh -m opencode-go/qwen3.8-flash` => exit_code=0, `last_message.txt` = PONG, session id captured.
- Real: `-v high` on qwen3.8-flash => `opencode error: Variant unavailable for opencode-go/qwen3.8-flash: high` (genuine opencode answer; shows error surfacing).
- Real edit task in a temp git repo: `git diff` shows `hello` -> `halo`, only `main` branch, no commits created by worker.

## Gaps (not verified)
- `--auto` behaviour/permission prompts on v2.2.7 not tested separately (wrapper passes `--auto` by default).
- `--resume`/`--fork` verified only against the stub, not real opencode.
- Parallel worktree flow (SKILL.md step 8) not run.
- Stub reflects behaviour observed on 2026-11-23 with v2.2.7; newer versions may differ.
- No pull request opened to upstream; upstream not notified.

## Lessons learned
- Third-party skills written for one CLI major version can silently break on the next; run one real end-to-end call right after install.
- Build the test stub from observed real output, not from the docs (docs split V1/V2).
- `uv init` inside a directory under an existing uv workspace attaches itself to it; use `--no-workspace`.
- Redacting secrets with sed by key name is unreliable; prefer not printing config files at all.
