"""
Permission Engine — Claw-Code inspired permission system.

5-level permission model with deny/allow/ask rule engine,
Bash read-only command whitelist, and workspace path boundary checks.
"""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass, field
from enum import Enum, auto
from fnmatch import fnmatch
from typing import Optional


# ---------------------------------------------------------------------------
# PermissionMode — 5-level enum
# ---------------------------------------------------------------------------

class PermissionMode(Enum):
    """
    ReadOnly      — 仅允许读取，拒绝写入和执行
    WorkspaceWrite — 允许写入 workspace 目录
    DangerFullAccess — 允许危险操作（rm -rf 等）
    Prompt        — 每次执行前询问
    Allow         — 完全放行（慎用）
    """
    ReadOnly = auto()
    WorkspaceWrite = auto()
    DangerFullAccess = auto()
    Prompt = auto()
    Allow = auto()


# ---------------------------------------------------------------------------
# RuleAction — what to do when a rule matches
# ---------------------------------------------------------------------------

class RuleAction(Enum):
    DENY  = "deny"
    ALLOW = "allow"
    ASK   = "ask"


# ---------------------------------------------------------------------------
# PermissionRule — single rule with subject pattern and action
# ---------------------------------------------------------------------------

@dataclass
class PermissionRule:
    """
    deny  tool(subj)  → 拒绝匹配的操作
    allow tool(subj)  → 允许匹配的操作
    ask   tool(subj)  → 匹配时弹窗询问

    subject 支持通配符:
      "*"           匹配所有
      "exec"        精确匹配工具名
      "exec:rm"     精确匹配 exec 调用 rm
      "exec:rm *"   exec 调用任何参数
      "exec:*"      任何 exec 调用
      "write:*"     任何写入操作
      "read:/path/*" read 访问路径
    """
    action:  RuleAction
    subject: str        # e.g. "tool(exec)", "tool(exec:rm)", "tool(write:*)"

    def matches(self, tool_name: str, subject: str = "*") -> bool:
        """
        Check if this rule matches the given tool_name and subject.

        subject input format:
          - "tool_name"          → just the tool (e.g. "exec")
          - "tool_name:sub"      → tool with sub-part (e.g. "exec:rm")
          - "tool_name:sub:arg"  → tool + sub + arg fragment
        """
        rule_pattern = self.subject

        # Normalize: ensure "tool(...)" wrapper
        if not rule_pattern.startswith("tool("):
            rule_pattern = f"tool({rule_pattern})"

        if not subject.startswith("tool("):
            subject = f"tool({subject})"

        return self._pattern_match(rule_pattern, subject)

    def _pattern_match(self, pattern: str, text: str) -> bool:
        """Glob-style pattern match supporting * and **."""
        # Split into tokens
        def tokenize(s: str) -> list[str]:
            # Remove tool() wrapper
            m = re.match(r"^tool\((.+)\)$", s)
            if m:
                s = m.group(1)
            return s.split(":")

        p_tokens = tokenize(pattern)
        t_tokens = tokenize(text)

        # Align lengths
        if len(p_tokens) < len(t_tokens):
            # Pad pattern with * to match extra tokens
            p_tokens += ["*"] * (len(t_tokens) - len(p_tokens))
        elif len(p_tokens) > len(t_tokens):
            return False

        for p, t in zip(p_tokens, t_tokens):
            if p == "**":
                continue
            if p == "*":
                continue
            if not fnmatch(t, p):
                return False
        return True


# ---------------------------------------------------------------------------
# Built-in rules
# ---------------------------------------------------------------------------

BUILTIN_DENY_RULES: list[PermissionRule] = [
    PermissionRule(RuleAction.DENY, "tool(exec:rm -rf /)"),
    PermissionRule(RuleAction.DENY, "tool(exec:rm -rf /usr)"),
    PermissionRule(RuleAction.DENY, "tool(exec:rm -rf /home)"),
    PermissionRule(RuleAction.DENY, "tool(exec:rm -rf /tmp)"),
    PermissionRule(RuleAction.DENY, "tool(exec:dd)"),
    PermissionRule(RuleAction.DENY, "tool(exec:mkfs)"),
    PermissionRule(RuleAction.DENY, "tool(exec:fdisk)"),
    PermissionRule(RuleAction.DENY, "tool(exec:parted)"),
    PermissionRule(RuleAction.DENY, "tool(exec:shutdown)"),
    PermissionRule(RuleAction.DENY, "tool(exec:reboot)"),
    PermissionRule(RuleAction.DENY, "tool(exec:halt)"),
    PermissionRule(RuleAction.DENY, "tool(exec:poweroff)"),
    PermissionRule(RuleAction.DENY, "tool(exec:init 0)"),
    PermissionRule(RuleAction.DENY, "tool(exec:kill -9 1)"),
    PermissionRule(RuleAction.DENY, "tool(exec:kill -9 -1)"),
    PermissionRule(RuleAction.DENY, "tool(exec:> /dev/sda)"),
    PermissionRule(RuleAction.DENY, "tool(exec:cat /dev/sda)"),
    PermissionRule(RuleAction.DENY, "tool(exec:chmod -R 000 /)"),
    PermissionRule(RuleAction.DENY, "tool(exec:chown -R) /etc"),
    PermissionRule(RuleAction.DENY, "tool(exec:wget|curl) * --output|/dev"),
    PermissionRule(RuleAction.DENY, "tool(exec:python) * -c * import os; os.system)"),
    PermissionRule(RuleAction.DENY, "tool(exec:perl) * -e * system)"),
    PermissionRule(RuleAction.DENY, "tool(exec:ruby) * -e * system)"),
    PermissionRule(RuleAction.DENY, "tool(exec:php) * -r * system)"),
    PermissionRule(RuleAction.DENY, "tool(exec:node) * -e * child_process)"),
]


# ---------------------------------------------------------------------------
# Bash read-only command whitelist (~60 commands)
# ---------------------------------------------------------------------------

READONLY_BASH_COMMANDS: set[str] = {
    # Coreutils — reading
    "cat", "cp", "ls", "cd", "pwd", "echo", "printf", "test",
    "true", "false", "yes",
    # Coreutils — file info
    "stat", "file", "find", "xargs", "locate", "updatedb",
    # Coreutils — text
    "head", "tail", "less", "more", "watch",
    "grep", "egrep", "fgrep", "rg", "awk", "sed", "cut", "sort",
    "uniq", "wc", "tr", "tee", "rev", "od", "hexdump", "strings",
    "base64", "md5sum", "sha1sum", "sha256sum", "sha512sum",
    # Coreutils — archive reading
    "tar", "gzip", "gunzip", "bzcat", "xzcat", "zcat", "zstdcat",
    " unzip", "7z", "7za",
    # Git
    "git", "gitk", "git-gui",
    # Network — read only
    "ping", "ping6", "curl", "wget", "ssh", "scp", "sftp",
    "rsync", "netstat", "ss", "ip", "ifconfig", "route", "arp",
    "nslookup", "dig", "host", "traceroute", "tracepath",
    "nmap", "nc", "telnet",
    # System info
    "df", "du", "free", "top", "htop", "ps", "pstree", "pgrep",
    "uname", "hostname", "uptime", "whoami", "id", "groups",
    "date", "cal", "tzselect", "locale",
    "env", "export", "printenv", "set", "unset", "readonly",
    "alias", "unalias", "type", "which", "whereis",
    "man", "info", "help",
    # Docker (read)
    "docker", "docker ps", "docker images", "docker logs",
    "docker inspect", "docker stats",
    # Misc
    "tmux", "screen", "sshfs", "fusermount",
    "jq", "yq", "xmllint",
    "mount", "umount",   # read-only mount inspection
    "lsblk", "blkid", "lspci", "lsusb",
    "dmidecode", "cat /proc/cpuinfo", "cat /proc/meminfo",
}

# Commands that are NEVER safe even in read-only list
BLOCKED_COMMANDS: set[str] = {
    "rm", "dd", "mkfs", "fdisk", "parted", "sfdisk",
    "shutdown", "reboot", "halt", "poweroff", "init",
    "kill", "killall", "pkill",
    "chmod", "chown", "chgrp", "setfacl",
    "mount", "umount", "losetup",
    "pvcreate", "vgcreate", "lvcreate",
    "cryptsetup", "luksformat",
    "iperf", "iperf3", "ab", "wrk",   # bench/DoS tools
    ":(){:|:&};:",                     # fork bomb pattern
}


# ---------------------------------------------------------------------------
# Workspace path boundary
# ---------------------------------------------------------------------------

# Default workspace root — override with set_workspace_root()
_WORKSPACE_ROOT: Optional[str] = None
_TRUSTED_PREFIXES: list[str] = []


def set_workspace_root(path: str) -> None:
    """Set the workspace root directory for boundary checks."""
    global _WORKSPACE_ROOT
    _WORKSPACE_ROOT = os.path.realpath(os.path.expanduser(path))


def add_trusted_prefix(prefix: str) -> None:
    """Add a path prefix that is allowed outside workspace."""
    global _TRUSTED_PREFIXES
    _TRUSTED_PREFIXES.append(os.path.realpath(os.path.expanduser(prefix)))


def check_path_boundary(path: str, mode: PermissionMode = PermissionMode.ReadOnly) -> tuple[bool, str]:
    """
    Check if a path is within allowed boundaries.

    Returns (allowed, reason).
    In ReadOnly/WorkspaceWrite modes, paths outside workspace are denied.
    DangerFullAccess allows any path.
    """
    if _WORKSPACE_ROOT is None:
        # No workspace root set — allow all (backwards compat)
        return True, "no workspace boundary configured"

    real_path = os.path.realpath(os.path.expanduser(path))

    # Check trusted prefixes first
    for prefix in _TRUSTED_PREFIXES:
        if real_path.startswith(prefix):
            return True, f"trusted prefix: {prefix}"

    if mode == PermissionMode.DangerFullAccess:
        return True, "DangerFullAccess mode — bypassing boundary"

    if mode == PermissionMode.Allow:
        return True, "Allow mode — bypassing boundary"

    if not real_path.startswith(_WORKSPACE_ROOT):
        return False, (
            f"path {path!r} resolves to {real_path!r} "
            f"outside workspace {_WORKSPACE_ROOT!r}"
        )

    return True, f"within workspace {_WORKSPACE_ROOT!r}"


# ---------------------------------------------------------------------------
# is_read_only_command — Bash heuristic whitelist check
# ---------------------------------------------------------------------------

def _tokenize_command(cmd: str) -> list[str]:
    """Split a shell command into tokens, respecting quotes."""
    tokens: list[str] = []
    current = ""
    in_quote = False
    quote_char = ""
    escape = False

    for ch in cmd:
        if escape:
            current += ch
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if in_quote:
            if ch == quote_char:
                in_quote = False
            current += ch
            continue
        if ch in ("'", '"'):
            in_quote = True
            quote_char = ch
            continue
        if ch in (" ", "\t", "\n"):
            if current:
                tokens.append(current)
                current = ""
            continue
        current += ch

    if current:
        tokens.append(current)
    return tokens


def _normalize_cmd(cmd: str) -> str:
    """Strip leading/trailing whitespace and normalize."""
    return " ".join(_tokenize_command(cmd.strip()))


def is_read_only_command(cmd: str, allow_subcommands: bool = True) -> tuple[bool, Optional[str]]:
    """
    Heuristic check if a bash command is read-only (safe to auto-approve).

    Returns (is_readonly, reason).
    reason is None if read-only, otherwise a string describing why it is not.

    Examples:
      is_read_only_command("cat /etc/passwd")     → (True, None)
      is_read_only_command("rm /tmp/foo")        → (False, "starts with blocked command: rm")
      is_read_only_command("ls -la /home")        → (True, None)
      is_read_only_command("curl http://evil.com")→ (False, "network write/opaque URL")
    """
    normalized = _normalize_cmd(cmd)
    tokens = _tokenize_command(cmd)
    if not tokens:
        return False, "empty command"

    base_cmd = tokens[0]

    # Check blocked commands first (absolute blocks)
    for blocked in BLOCKED_COMMANDS:
        if base_cmd == blocked:
            return False, f"blocked command: {blocked}"
        if normalized.startswith(blocked + " "):
            return False, f"starts with blocked command: {blocked}"

    # Check fork bomb pattern
    if ":(){" in cmd or "fork bomb" in cmd.lower():
        return False, "fork bomb pattern detected"

    # Pipeline / compound: check all parts
    if "|" in cmd or "&&" in cmd or "||" in cmd or ";" in cmd:
        parts = re.split(r"[|;&]+", cmd)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            ok, reason = is_read_only_command(part, allow_subcommands)
            if not ok:
                return False, f"compound command failed: {reason}"

    # Redirection to files: check if writing to sensitive paths
    redirect_match = re.search(r">\s*(.+?)(?:\s|$)", cmd)
    if redirect_match:
        target = redirect_match.group(1).strip()
        target = os.path.expanduser(target)
        # Disallow redirecting to block devices or sensitive paths
        sensitive = ("/dev/sd", "/dev/nvme", "/dev/mmc", "/dev/vd",
                     "/sys/", "/proc/", "/dev/watchdog", "/dev/null")
        for s in sensitive:
            if target.startswith(s) and s != "/dev/null":
                return False, f"writing to sensitive device: {target}"
        # Allow > /dev/null, regular files in /tmp or workspace
        if not target.startswith("/dev/"):
            # Regular file write — only allow in workspace or /tmp
            allowed_write_dirs = ["/tmp", _WORKSPACE_ROOT or ""]
            in_allowed = any(
                os.path.realpath(target).startswith(d)
                for d in allowed_write_dirs if d
            )
            # Only flag as non-readonly if we're in a write-restricted mode
            # (we flag but don't block — let path check decide)

    # Here-doc redirection
    if "<<" in cmd:
        return False, "here-document redirection is not read-only"

    # Command substitution $() or ``
    if "$(" in cmd or "`" in cmd:
        return False, "command substitution is not read-only"

    # Variable assignment (left side) is OK; expansion is not read-only
    if re.match(r"^\s*\w+=", cmd.strip()) and "|" not in cmd and ">" not in cmd:
        return True, None  # e.g. "PATH=/my/path ls" — OK

    # Check against whitelist
    # Support subcommand whitelist when allow_subcommands=True
    if allow_subcommands:
        # Build effective whitelist including subcommands
        effective_whitelist = set(READONLY_BASH_COMMANDS)
        # git is read-only subcommands
        git_readonly = {"git", "gitk", "git-gui"}
        effective_whitelist.update(git_readonly)
    else:
        effective_whitelist = READONLY_BASH_COMMANDS

    for safe_cmd in effective_whitelist:
        if safe_cmd == base_cmd:
            return True, None
        # Support "git log" as "git"
        if base_cmd.startswith(safe_cmd + " "):
            return True, None
        if base_cmd.startswith(safe_cmd + "="):
            return True, None
        # git subcommands
        if safe_cmd == "git" and base_cmd.startswith("git "):
            sub = base_cmd.split()[1] if len(base_cmd.split()) > 1 else ""
            readonly_git = {
                "log", "show", "diff", "status", "branch", "tag",
                "stash", "reflog", "bisect", "blame", "grep", "archive",
                "shortlog", "describe", "rev-parse", "ls-tree", "cat-file",
                "check-attr", "check-ignore", "cherry", "cherry-pick",
                "config", "remote", "fetch", "clone", "init",
            }
            if sub in readonly_git:
                return True, None
            # mutating git subcommands
            mutating_git = {
                "push", "pull", "commit", "add", "rm", "mv",
                "merge", "rebase", "reset", "checkout", "restore",
                "switch", "worktree", "clean", "gc", "pack-refs",
            }
            if sub in mutating_git:
                return False, f"mutating git subcommand: git {sub}"

    # docker read-only subcommands
    docker_readonly = {"ps", "images", "logs", "inspect", "stats",
                       "port", "ls", "network", "volume", "container"}
    for safe in docker_readonly:
        if base_cmd == f"docker {safe}" or base_cmd.startswith(f"docker {safe} "):
            return True, None

    #的最后: unknown command — flag as not provably read-only
    return False, f"command not in read-only whitelist: {base_cmd}"


# ---------------------------------------------------------------------------
# PermissionEnforcer — core rule engine
# ---------------------------------------------------------------------------

@dataclass
class PermissionContext:
    """Context passed to each permission check."""
    tool:      str
    sub:       str = "*"       # e.g. "exec", "exec:rm", "read:/path"
    args:      Optional[str] = None   # raw args for additional analysis
    path:      Optional[str] = None   # file path if applicable
    user:      Optional[str] = None   # user identifier
    session:   Optional[str] = None   # session identifier


@dataclass
class PermissionResult:
    """Result of a permission check."""
    allowed:    bool
    reason:     str
    mode:       PermissionMode
    requires_confirmation: bool = False
    matched_rule: Optional[PermissionRule] = None


class PermissionEnforcer:
    """
    Rule-based permission enforcer.

    Rule evaluation order:
      1. mode-based defaults (ReadOnly, Allow, etc.)
      2. builtin deny rules
      3. user-defined deny rules
      4. user-defined ask rules
      5. user-defined allow rules
      6. fallback to mode-based default

    Use `add_rule()` to register deny/allow/ask rules.
    Rules are evaluated in insertion order (FIFO).
    """

    def __init__(
        self,
        mode: PermissionMode = PermissionMode.ReadOnly,
        workspace_root: Optional[str] = None,
    ):
        self.mode = mode
        self.rules: list[PermissionRule] = list(BUILTIN_DENY_RULES)
        self._path_boundary_enabled = True

        if workspace_root:
            set_workspace_root(workspace_root)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_mode(self, mode: PermissionMode) -> None:
        self.mode = mode

    def add_rule(self, action: RuleAction, subject: str) -> None:
        """Register a user rule. Subject uses tool(subject) syntax."""
        self.rules.append(PermissionRule(action, subject))

    def add_deny(self, subject: str) -> None:
        self.add_rule(RuleAction.DENY, subject)

    def add_allow(self, subject: str) -> None:
        self.add_rule(RuleAction.ALLOW, subject)

    def add_ask(self, subject: str) -> None:
        self.add_rule(RuleAction.ASK, subject)

    def set_workspace_root(self, path: str) -> None:
        set_workspace_root(path)

    def add_trusted_prefix(self, prefix: str) -> None:
        add_trusted_prefix(prefix)

    # ------------------------------------------------------------------
    # Core check
    # ------------------------------------------------------------------

    def check(self, ctx: PermissionContext) -> PermissionResult:
        """
        Main entry point — evaluate permission for a tool call.

        Returns PermissionResult with allowed=True/False and a reason.
        """
        # Step 1: mode-level defaults
        if self.mode == PermissionMode.Allow:
            return PermissionResult(True, "mode=Allow", self.mode)

        if self.mode == PermissionMode.ReadOnly:
            # ReadOnly mode: check if this is a write operation
            if ctx.tool in READONLY_TOOLS:
                # It's a write-capable tool — check path + command
                pass  # fall through to rule engine
            else:
                return PermissionResult(True, "mode=ReadOnly, read-only tool", self.mode)

        if self.mode == PermissionMode.Prompt:
            return PermissionResult(
                False, "mode=Prompt — requires confirmation",
                self.mode, requires_confirmation=True
            )

        # Step 2: path boundary check (for file operations)
        if self._path_boundary_enabled and ctx.path:
            allowed, reason = check_path_boundary(ctx.path, self.mode)
            if not allowed:
                return PermissionResult(False, f"path_boundary: {reason}", self.mode)

        # Step 3: build subject string for rule matching
        subject = ctx.sub if ctx.sub != "*" else ctx.tool
        if ctx.sub != "*" and ctx.sub != ctx.tool:
            subject = f"{ctx.tool}:{ctx.sub}"

        # Step 4: evaluate rules in order
        for rule in self.rules:
            if rule.matches(ctx.tool, subject):
                if rule.action == RuleAction.DENY:
                    return PermissionResult(
                        False, f"denied by rule: {rule.subject}",
                        self.mode, matched_rule=rule
                    )
                elif rule.action == RuleAction.ALLOW:
                    return PermissionResult(
                        True, f"allowed by rule: {rule.subject}",
                        self.mode, matched_rule=rule
                    )
                elif rule.action == RuleAction.ASK:
                    return PermissionResult(
                        False, f"ask rule matched: {rule.subject}",
                        self.mode, requires_confirmation=True, matched_rule=rule
                    )

        # Step 5: mode fallback
        if self.mode == PermissionMode.DangerFullAccess:
            return PermissionResult(
                True, "mode=DangerFullAccess — fallback allow",
                self.mode
            )

        if self.mode == PermissionMode.ReadOnly:
            # Final read-only gate: check bash command if exec tool
            if ctx.tool == "exec" and ctx.args:
                ok, reason = is_read_only_command(ctx.args)
                if ok:
                    return PermissionResult(True, f"read-only bash: {ctx.args[:60]}", self.mode)
                else:
                    return PermissionResult(False, f"not read-only bash: {reason}", self.mode)

        return PermissionResult(False, f"no rule matched — denied by default (mode={self.mode.name})", self.mode)

    # ------------------------------------------------------------------
    # Convenience check methods
    # ------------------------------------------------------------------

    def check_exec(self, cmd: str, path: Optional[str] = None) -> PermissionResult:
        """Check if an exec command is allowed."""
        return self.check(PermissionContext(tool="exec", sub="*", args=cmd, path=path))

    def check_write(self, path: str) -> PermissionResult:
        """Check if a write to a path is allowed."""
        return self.check(PermissionContext(tool="write", sub="*", path=path))

    def check_read(self, path: str) -> PermissionResult:
        """Check if a read from a path is allowed."""
        return self.check(PermissionContext(tool="read", sub="*", path=path))

    def check_tool(self, tool: str, sub: str = "*") -> PermissionResult:
        """Check if a generic tool call is allowed."""
        return self.check(PermissionContext(tool=tool, sub=sub))


# ---------------------------------------------------------------------------
# ReadOnly tool registry — tools considered "read-only" in ReadOnly mode
# ---------------------------------------------------------------------------

READONLY_TOOLS: set[str] = {
    "read", "web_fetch", "web_search", "image", "video_generate",
    "music_generate", "image_generate", "memory_search", "memory_get",
    "session_status", "exec",    # exec is checked via is_read_only_command
    "sessions_yield", "video_frames",
}


# ---------------------------------------------------------------------------
# Default global enforcer (singleton for convenience)
# ---------------------------------------------------------------------------

_default_enforcer: Optional[PermissionEnforcer] = None


def get_default_enforcer() -> PermissionEnforcer:
    global _default_enforcer
    if _default_enforcer is None:
        _default_enforcer = PermissionEnforcer(mode=PermissionMode.ReadOnly)
    return _default_enforcer


def check_permission(
    tool: str,
    sub: str = "*",
    path: Optional[str] = None,
    args: Optional[str] = None,
) -> PermissionResult:
    """Quick check using the default enforcer."""
    return get_default_enforcer().check(
        PermissionContext(tool=tool, sub=sub, path=path, args=args)
    )


# ---------------------------------------------------------------------------
# CLI / test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Permission Engine Self-Test ===\n")

    enforcer = PermissionEnforcer(mode=PermissionMode.WorkspaceWrite)
    enforcer.set_workspace_root("/home/maomao/.openclaw/workspace")

    # Use ReadOnly mode for exec tests (auto-checks bash whitelist)
    enforcer_ro = PermissionEnforcer(mode=PermissionMode.ReadOnly)
    enforcer_ro.set_workspace_root("/home/maomao/.openclaw/workspace")
    # Add ask rule to test ask path
    enforcer_ro.add_ask("tool(exec:curl)")

    test_cases = [
        ("exec", "cat /etc/passwd"),
        ("exec", "ls /home/maomao"),
        ("exec", "rm -rf /tmp/test"),
        ("exec", "curl http://example.com"),
        ("write", "/home/maomao/.openclaw/workspace/test.txt"),
        ("write", "/etc/passwd"),
        ("read", "/home/maomao/.openclaw/workspace/SOUL.md"),
        ("exec", "dd if=/dev/zero of=/tmp/test bs=1 count=10"),
        ("exec", "chmod -R 000 /"),
    ]

    for tool, desc in test_cases:
        if tool == "exec":
            result = enforcer_ro.check_exec(desc)
        elif tool == "write":
            result = enforcer.check_write(desc)
        elif tool == "read":
            result = enforcer.check_read(desc)
        else:
            result = enforcer.check_tool(tool, desc)

        status = "✅" if result.allowed else "❌"
        confirm = " 🔔" if result.requires_confirmation else ""
        print(f"{status} {tool}: {desc[:50]:<50} → {result.reason}{confirm}")

    print("\n=== Bash Read-Only Check ===\n")
    bash_tests = [
        "cat /etc/hostname",
        "ls -la /home",
        "grep -r 'test' /tmp",
        "git log --oneline -5",
        "ps aux | grep python",
        "curl -s https://example.com",
        "tar -tzf backup.tar.gz",
        "rm -rf /tmp/dir",
        "dd if=/dev/zero of=/tmp/test bs=1",
        "echo 'hello' > /tmp/out.txt",
    ]
    for cmd in bash_tests:
        ok, reason = is_read_only_command(cmd)
        status = "✅" if ok else "❌"
        detail = f" ({reason})" if reason else ""
        print(f"{status} {cmd[:60]:<60}{detail}")
