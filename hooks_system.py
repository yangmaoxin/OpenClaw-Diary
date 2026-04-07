"""
Hook System for OpenClaw Agent.

Provides a plugin-style hook mechanism with three trigger points:
- PreToolUse:  Called before a tool is executed (can modify input or deny)
- PostToolUse: Called after a tool succeeds (can inspect output)
- PostToolUseFailure: Called after a tool fails (can inspect error)

Exit code semantics:
  0  → allow / continue (hook had no objection)
  2  → deny (only for PreToolUse; causes tool call to be rejected)
  other → failure (hook itself errored; treated as non-fatal warning)

When a PreToolUse hook exits 0 it may also write a modified JSON payload
to stdout to replace the original tool input (updated_input).

For all other hooks stdout/stderr is collected as messages attached to
HookResult.

Payload format passed via stdin JSON + environment variables (see below).

Configuration is loaded from hooks_config.yaml in the same directory.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml

# ─────────────────────────────────────────────────────────────────────────────
# Types
# ─────────────────────────────────────────────────────────────────────────────


class HookTrigger(Enum):
    """
    Three hook trigger points mirroring Claw-Code / Claude Code semantics.

    PreToolUse       – fires before the tool runs; hook may rewrite input.
    PostToolUse      – fires after a successful tool call.
    PostToolUseFailure – fires after a tool call that returned an error.
    """

    PreToolUse = "PreToolUse"
    PostToolUse = "PostToolUse"
    PostToolUseFailure = "PostToolUseFailure"


@dataclass
class HookResult:
    """
    Result returned by a single hook script invocation.

    Attributes
    ----------
    denied : bool
        True when the hook explicitly rejected the action (exit code 2 on
        PreToolUse).  A denied PreToolUse prevents the tool from running.
    failed : bool
        True when the hook itself crashed or returned a non-zero, non-2 exit
        code.  Failures are non-fatal; they are surfaced as warning messages
        but never block the tool.
    messages : list[str]
        Combined stdout + stderr lines collected from the hook script.
    updated_input : dict | None
        For PreToolUse only: if the hook wrote a valid JSON object to stdout
        this field carries the replacement tool input.  None means "no change".
    """

    denied: bool = False
    failed: bool = False
    messages: list[str] = field(default_factory=list)
    updated_input: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────────────
# HookRunner
# ─────────────────────────────────────────────────────────────────────────────


class HookRunner:
    """
    Loads hook definitions from a YAML config file and executes matching
    hook scripts at the appropriate trigger point.

    Parameters
    ----------
    config_path : str | Path
        Path to the hooks_config.yaml file.
    """

    # Keys that are always passed as environment variables (shortcut access)
    _ENV_KEYS = frozenset(
        [
            "HOOK_TRIGGER",
            "TOOL_NAME",
            "TOOL_INPUT",
            "TOOL_INPUT_JSON",
            "TOOL_OUTPUT",
            "TOOL_ERROR",
            "AGENT_ID",
            "SESSION_ID",
        ]
    )

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            config_path = Path(__file__).parent / "hooks_config.yaml"
        self._config_path = Path(config_path)
        self._configs: list[dict] = []
        self._load_config()

    # ── public API ────────────────────────────────────────────────────────────

    def run_pre_tool_use(
        self,
        tool_name: str,
        tool_input: dict,
        agent_id: str = "",
        session_id: str = "",
    ) -> HookResult:
        """
        Run PreToolUse hooks for the named tool.

        Parameters
        ----------
        tool_name:
            Name of the tool being invoked (e.g. "exec", "read").
        tool_input:
            Raw input dictionary that will be passed to the tool.
        agent_id, session_id:
            Optional identifiers for logging / conditional scripts.

        Returns
        -------
        HookResult
            Aggregated result across all matching hooks.  ``updated_input``
            contains the replacement dict if the last ran hook wrote one.
        """
        payload = self._build_payload(
            trigger=HookTrigger.PreToolUse,
            tool_name=tool_name,
            tool_input=tool_input,
            agent_id=agent_id,
            session_id=session_id,
        )
        return self._run_hooks(trigger=HookTrigger.PreToolUse, payload=payload)

    def run_post_tool_use(
        self,
        tool_name: str,
        tool_input: dict,
        tool_output: Any,
        agent_id: str = "",
        session_id: str = "",
    ) -> HookResult:
        """
        Run PostToolUse hooks after a successful tool call.

        Parameters
        ----------
        tool_name, tool_input:
            The tool that was invoked.
        tool_output:
            Whatever the tool returned (serialised to JSON for the hook).
        agent_id, session_id:
            Optional identifiers.
        """
        payload = self._build_payload(
            trigger=HookTrigger.PostToolUse,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            agent_id=agent_id,
            session_id=session_id,
        )
        return self._run_hooks(trigger=HookTrigger.PostToolUse, payload=payload)

    def run_post_tool_use_failure(
        self,
        tool_name: str,
        tool_input: dict,
        tool_error: str,
        agent_id: str = "",
        session_id: str = "",
    ) -> HookResult:
        """
        Run PostToolUseFailure hooks after a tool call that raised an error.

        Parameters
        ----------
        tool_name, tool_input:
            The tool that was invoked.
        tool_error:
            Error message or traceback string.
        agent_id, session_id:
            Optional identifiers.
        """
        payload = self._build_payload(
            trigger=HookTrigger.PostToolUseFailure,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_error=tool_error,
            agent_id=agent_id,
            session_id=session_id,
        )
        return self._run_hooks(
            trigger=HookTrigger.PostToolUseFailure, payload=payload
        )

    def reload(self) -> None:
        """Re-read the configuration file (useful for live-reload in dev)."""
        self._load_config()

    # ── internal ───────────────────────────────────────────────────────────────

    def _load_config(self) -> None:
        if not self._config_path.exists():
            self._configs = []
            return
        with open(self._config_path, encoding="utf-8") as fh:
            raw: dict = yaml.safe_load(fh) or {}
        self._configs = raw.get("hooks", [])

    def _build_payload(
        self,
        trigger: HookTrigger,
        tool_name: str,
        tool_input: dict,
        tool_output: Any = None,
        tool_error: str = "",
        agent_id: str = "",
        session_id: str = "",
    ) -> dict:
        return {
            "trigger": trigger.value,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "tool_error": tool_error,
            "agent_id": agent_id,
            "session_id": session_id,
        }

    def _run_hooks(self, trigger: HookTrigger, payload: dict) -> HookResult:
        """
        Execute every hook whose trigger matches, in definition order.
        Results are folded into a single HookResult.
        """
        result = HookResult()

        matching = [c for c in self._configs if c.get("trigger") == trigger.value]
        if not matching:
            return result

        for cfg in matching:
            # Optional tool-name matcher (glob-style)
            if not self._match_tool(cfg.get("tool_name"), payload["tool_name"]):
                continue

            hook_cfg = cfg.get("hook", {})
            cmd = hook_cfg.get("command") or hook_cfg.get("script")
            if not cmd:
                continue

            single = self._invoke(cmd, payload, trigger)
            result.messages.extend(single.messages)

            if single.denied:
                result.denied = True
                # Short-circuit: once denied, stop processing further hooks
                break

            if single.failed:
                result.failed = True

            # Use the last hook's updated_input if present
            if single.updated_input is not None:
                result.updated_input = single.updated_input

        return result

    def _match_tool(self, pattern: Optional[str], tool_name: str) -> bool:
        """Glob-style match; empty/None pattern matches everything."""
        if not pattern:
            return True
        import fnmatch

        return fnmatch.fnmatch(tool_name, pattern)

    def _invoke(
        self, command: str, payload: dict, trigger: HookTrigger
    ) -> HookResult:
        """
        Run a single hook command with payload passed via stdin + env vars.
        Returns HookResult based on exit code semantics.
        """
        # Build env — always include the shortcut keys
        env = {k: os.environ.get(k, "") for k in self._ENV_KEYS}
        env.update(
            {
                "HOOK_TRIGGER": trigger.value,
                "TOOL_NAME": payload["tool_name"],
                "TOOL_INPUT_JSON": json.dumps(payload["tool_input"], ensure_ascii=False),
                "AGENT_ID": payload.get("agent_id", ""),
                "SESSION_ID": payload.get("session_id", ""),
            }
        )
        # Additional fields
        if payload.get("tool_output") is not None:
            env["TOOL_OUTPUT"] = (
                json.dumps(payload["tool_output"], ensure_ascii=False, default=str)
            )
        if payload.get("tool_error"):
            env["TOOL_ERROR"] = payload["tool_error"]

        stdin_data = json.dumps(payload, ensure_ascii=False, default=str)

        try:
            proc = subprocess.run(
                command,
                shell=True,
                input=stdin_data,
                cwd=self._config_path.parent,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return HookResult(failed=True, messages=["Hook timed out after 30s"])
        except OSError as exc:
            return HookResult(failed=True, messages=[f"Hook launch failed: {exc}"])

        stdout_lines = proc.stdout.strip().splitlines() if proc.stdout.strip() else []
        stderr_lines = proc.stderr.strip().splitlines() if proc.stderr.strip() else []
        all_lines = stdout_lines + [f"[stderr] {l}" for l in stderr_lines]

        rc = proc.returncode

        if rc == 0:
            # Possible updated_input on stdout (PreToolUse only)
            updated = None
            if trigger == HookTrigger.PreToolUse and stdout_lines:
                try:
                    candidate = json.loads(stdout_lines[0])
                    if isinstance(candidate, dict):
                        updated = candidate
                except json.JSONDecodeError:
                    pass  # not JSON; treat as regular message
            return HookResult(messages=all_lines, updated_input=updated)

        if rc == 2:
            # Explicit denial (only meaningful for PreToolUse)
            return HookResult(denied=True, failed=False, messages=all_lines)

        # Any other non-zero exit → hook itself failed
        return HookResult(failed=True, messages=all_lines)


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrapper – mirrors how an agent integration would call the runner
# ─────────────────────────────────────────────────────────────────────────────


def pre_tool(tool_name: str, tool_input: dict, **kwargs) -> HookResult:
    """Shorthand for HookRunner().run_pre_tool_use(...)."""
    return HookRunner().run_pre_tool_use(tool_name, tool_input, **kwargs)


def post_tool(tool_name: str, tool_input: dict, tool_output: Any, **kwargs) -> HookResult:
    """Shorthand for HookRunner().run_post_tool_use(...)."""
    return HookRunner().run_post_tool_use(tool_name, tool_input, tool_output, **kwargs)


def post_tool_failure(
    tool_name: str, tool_input: dict, tool_error: str, **kwargs
) -> HookResult:
    """Shorthand for HookRunner().run_post_tool_use_failure(...)."""
    return HookRunner().run_post_tool_use_failure(tool_name, tool_input, tool_error, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Self-test (run directly)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(textwrap.dedent("""
        Hook System – self-test
        ──────────────────────
        This module implements three hook trigger points:

          PreToolUse        → before tool execution; exit 2 = deny, stdout JSON = new input
          PostToolUse       → after successful tool; exit 2 = n/a (treated as failure)
          PostToolUseFailure → after failed tool;    exit 2 = n/a (treated as failure)

        Exit codes:
          0  allow / continue
          2  deny (PreToolUse only)
          other → failure (non-fatal warning)

        Configuration: same-dir/hooks_config.yaml
        Payload:       stdin JSON  +  env vars (TOOL_NAME, TOOL_INPUT_JSON, …)

        Import and create a HookRunner() to use programmatically.
        """)
    )
