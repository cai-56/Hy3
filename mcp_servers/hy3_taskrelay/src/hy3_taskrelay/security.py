"""Credential redaction at the TaskRelay trust boundary."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

REDACTED = "[REDACTED]"
_IDENTIFIER_KEYS = {
    "schema_version",
    "evidence_id",
    "evidence_ids",
    "checkpoint_id",
    "finding_id",
    "resume_id",
}
_SENSITIVE_IDENTIFIER_KEYS = _IDENTIFIER_KEYS - {"schema_version"}

_PREFIX_PATTERNS = (
    re.compile(
        r"(?i)((?:\"|')?authorization(?:\"|')?\s*[:=]\s*)"
        r"(\"[^\"]*\"|'[^']*'|[^\r\n]+)"
    ),
    re.compile(
        r"(?i)((?:\"|')?(?:connection[_-]?string|database[_-]?url)(?:\"|')?"
        r"\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\r\n]+)"
    ),
    re.compile(
        r"(?i)((?:\"|')?(?:set[_-]?)?cookie(?:\"|')?\s*[:=]\s*(?:\"|')?)"
        r"([^\"'\r\n]+)"
    ),
    re.compile(
        r"(?i)((?:\"|')?\b(?:(?:aws[_-]?)?secret[_-]?access[_-]?key|"
        r"account[_-]?key|shared[_-]?access[_-]?signature|"
        r"(?:access|refresh|session|id)[_-]?token|client[_-]?secret|"
        r"(?:[a-z0-9]+[_-]){0,8}(?:api[_-]?key|private[_-]?key|token|password|secret))\b"
        r"(?:\"|')?\s*[:=]\s*)"
        r"(\"[^\"]*\"|'[^']*'|[^\s,;}\]]+)"
    ),
)
_WHOLE_PATTERNS = (
    re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bAKID[A-Za-z0-9]{12,}\b"),
    re.compile(r"(?i)\b[A-Za-z][A-Za-z0-9+.-]{0,31}://[^\s/@:]*:[^\s/@]+@[^\s\"']+"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
)


def _consume_csi(value: str, index: int) -> int:
    while index < len(value):
        codepoint = ord(value[index])
        index += 1
        if 0x40 <= codepoint <= 0x7E:
            break
    return index


def _consume_osc(value: str, index: int) -> int:
    while index < len(value):
        if value[index] in {"\x07", "\x9c"}:
            return index + 1
        if value[index] == "\x1b" and index + 1 < len(value) and value[index + 1] == "\\":
            return index + 2
        index += 1
    return index


def _strip_terminal_controls(value: str) -> str:
    """Remove terminal escape sequences and unsafe C0/C1 controls in one bounded pass."""

    output: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        codepoint = ord(character)
        if character == "\x1b":
            index += 1
            if index >= len(value):
                break
            if value[index] == "[":
                index = _consume_csi(value, index + 1)
                continue
            if value[index] == "]":
                index = _consume_osc(value, index + 1)
                continue
            while index < len(value) and 0x20 <= ord(value[index]) <= 0x2F:
                index += 1
            if index < len(value) and 0x30 <= ord(value[index]) <= 0x7E:
                index += 1
            continue
        if character == "\x9b":
            index = _consume_csi(value, index + 1)
            continue
        if character == "\x9d":
            index = _consume_osc(value, index + 1)
            continue
        if codepoint < 32 and character not in {"\n", "\t"}:
            index += 1
            continue
        if 127 <= codepoint <= 159:
            index += 1
            continue
        output.append(character)
        index += 1
    return "".join(output)


def _redact_prefixed(match: re.Match[str]) -> str:
    value = match.group(2)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return f"{match.group(1)}{value[0]}{REDACTED}{value[-1]}"
    return f"{match.group(1)}{REDACTED}"


def redact_text(value: str, secret_values: Iterable[str] = ()) -> str:
    """Replace common credentials and explicitly supplied secrets without logging them."""

    redacted = _strip_terminal_controls(value)
    for secret in secret_values:
        if len(secret) >= 4:
            redacted = redacted.replace(secret, REDACTED)
    for pattern in _PREFIX_PATTERNS:
        redacted = pattern.sub(_redact_prefixed, redacted)
    for pattern in _WHOLE_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact_data(value: Any, secret_values: Iterable[str] = ()) -> Any:
    """Recursively redact every string value while preserving the data shape."""

    if isinstance(value, str):
        return redact_text(value, secret_values)
    if isinstance(value, Mapping):
        return {
            key: item if key in _IDENTIFIER_KEYS else redact_data(item, secret_values)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_data(item, secret_values) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_data(item, secret_values) for item in value)
    return value


def contains_sensitive_identifier(value: Any, secret_values: Iterable[str] = ()) -> bool:
    """Return whether an identifier embeds credential material that cannot be rewritten safely."""

    secrets = tuple(secret_values)
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _SENSITIVE_IDENTIFIER_KEYS:
                identifiers = item if isinstance(item, (list, tuple)) else (item,)
                if any(
                    isinstance(identifier, str) and redact_text(identifier, secrets) != identifier
                    for identifier in identifiers
                ):
                    return True
            if contains_sensitive_identifier(item, secrets):
                return True
    elif isinstance(value, (list, tuple)):
        return any(contains_sensitive_identifier(item, secrets) for item in value)
    return False
