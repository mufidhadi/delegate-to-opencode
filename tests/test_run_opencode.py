"""Behavioural tests for scripts/run-opencode.sh against opencode v2 semantics.

A stub `opencode` on PATH mimics what v2.2.7 was observed to do:
  - rejects the flags `--dir` and `--variant` (exit 1, "Unrecognized flag")
  - emits NDJSON where assistant text lives in `.part.text`
  - ends a successful run with a `step_finish` event
  - exits 1 and emits an `error` event on provider failure
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run-opencode.sh"

STUB = r"""#!/usr/bin/env bash
printf '%s\n' "$@" > "$STUB_ARGS_FILE"
pwd > "$STUB_PWD_FILE"
for a in "$@"; do
  case "$a" in
    --dir|--variant) echo "ERROR"; echo "  Unrecognized flag: $a in command opencode run" >&2; exit 1 ;;
  esac
done
if [[ "${STUB_MODE:-ok}" == "error" ]]; then
  echo '{"type":"step_start","sessionID":"ses_stub","part":{"type":"step-start"}}'
  echo '{"type":"error","sessionID":"ses_stub","error":{"type":"provider.quota","message":"Insufficient Balance"}}'
  exit 1
fi
echo '{"type":"step_start","sessionID":"ses_stub","part":{"type":"step-start"}}'
echo '{"type":"text","sessionID":"ses_stub","part":{"type":"text","text":"PONG"}}'
echo '{"type":"step_finish","sessionID":"ses_stub","part":{"type":"step-finish","reason":"stop"}}'
"""


@pytest.fixture
def env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "opencode"
    stub.write_text(STUB)
    stub.chmod(0o755)
    e = os.environ.copy()
    e["PATH"] = f"{bin_dir}:{e['PATH']}"
    e["OPENCODE_ROUTER_RUNS"] = str(tmp_path / "runs")
    e["STUB_ARGS_FILE"] = str(tmp_path / "args.txt")
    e["STUB_PWD_FILE"] = str(tmp_path / "pwd.txt")
    e.pop("OPENCODE_ROUTER_MODEL", None)
    e.pop("OPENCODE_ROUTER_VARIANT", None)
    return e


def run(env, *args, prompt="do it"):
    return subprocess.run(
        [str(SCRIPT), *args, "-"], input=prompt, capture_output=True, text=True, env=env
    )


def run_dir(proc):
    for line in proc.stdout.splitlines():
        if line.startswith("RUN_DIR="):
            return Path(line.split("=", 1)[1])
    raise AssertionError(f"no RUN_DIR in output: {proc.stdout!r}")


def stub_args(env):
    return Path(env["STUB_ARGS_FILE"]).read_text().splitlines()


def test_success_run_never_passes_unsupported_flags(env, tmp_path):
    proc = run(env, "-C", str(tmp_path), "-m", "opencode-go/qwen3.8-flash")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "--dir" not in stub_args(env)
    assert "--variant" not in stub_args(env)


def test_workdir_is_applied_by_changing_directory(env, tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    run(env, "-C", str(target), "-m", "opencode-go/qwen3.8-flash")
    assert Path(env["STUB_PWD_FILE"]).read_text().strip() == str(target.resolve())


def test_variant_is_appended_to_model(env, tmp_path):
    run(env, "-C", str(tmp_path), "-m", "opencode-go/qwen3.8-flash", "-v", "high")
    args = stub_args(env)
    assert args[args.index("-m") + 1] == "opencode-go/qwen3.8-flash#high"


def test_variant_from_env_is_appended_to_model(env, tmp_path):
    env["OPENCODE_ROUTER_VARIANT"] = "max"
    run(env, "-C", str(tmp_path), "-m", "opencode-go/qwen3.8-flash")
    args = stub_args(env)
    assert args[args.index("-m") + 1] == "opencode-go/qwen3.8-flash#max"


def test_variant_without_model_is_rejected(env, tmp_path):
    proc = run(env, "-C", str(tmp_path), "-v", "high")
    assert proc.returncode == 2
    assert "variant" in proc.stderr.lower()


def test_last_message_is_read_from_part_text(env, tmp_path):
    proc = run(env, "-C", str(tmp_path), "-m", "opencode-go/qwen3.8-flash")
    d = run_dir(proc)
    assert (d / "last_message.txt").read_text() == "PONG"
    assert "PONG" in proc.stdout


def test_session_id_is_captured(env, tmp_path):
    proc = run(env, "-C", str(tmp_path), "-m", "opencode-go/qwen3.8-flash")
    assert (run_dir(proc) / "session_id").read_text().strip() == "ses_stub"


def test_meta_json_records_terminal_event_on_success(env, tmp_path):
    proc = run(env, "-C", str(tmp_path), "-m", "opencode-go/qwen3.8-flash")
    meta = json.loads((run_dir(proc) / "meta.json").read_text())
    assert meta["type"] == "step_finish"


def test_provider_error_is_surfaced_with_nonzero_exit(env, tmp_path):
    env["STUB_MODE"] = "error"
    proc = run(env, "-C", str(tmp_path), "-m", "opencode-go/qwen3.8-flash")
    assert proc.returncode != 0
    assert "Insufficient Balance" in proc.stdout
    meta = json.loads((run_dir(proc) / "meta.json").read_text())
    assert meta["type"] == "error"


def test_resume_passes_session_flag(env, tmp_path):
    run(env, "-C", str(tmp_path), "-m", "opencode-go/qwen3.8-flash", "--resume", "ses_abc")
    args = stub_args(env)
    assert args[args.index("-s") + 1] == "ses_abc"
