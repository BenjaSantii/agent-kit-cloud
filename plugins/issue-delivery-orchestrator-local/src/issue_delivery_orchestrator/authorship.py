"""Decide whether a review comment is automated, independent of the author login."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .config import settings

_GENERIC_BOT_LOGIN = re.compile(r"(?:\[bot\]|[-_]bot)$")


@dataclass(frozen=True)
class Authorship:
    automated: bool
    source: str
    signal: str
    login: str


def comment_login(comment: dict[str, Any]) -> str:
    holder = comment.get("user") or comment.get("author") or {}
    return str(holder.get("login") or "").strip()


def comment_body(comment: dict[str, Any]) -> str:
    return str(comment.get("body") or comment.get("bodyText") or "")


def classify(comment: dict[str, Any]) -> Authorship:
    login = comment_login(comment)
    lowered = login.lower()
    configuration = settings()

    for name in configuration.bot_names:
        if name and name in lowered:
            return Authorship(True, name, "login", login)
    if _GENERIC_BOT_LOGIN.search(lowered):
        return Authorship(True, "bot", "login", login)

    body = comment_body(comment)
    for signature in configuration.automated_signatures:
        if signature.pattern.search(body):
            return Authorship(True, signature.name, "body-signature", login)

    return Authorship(False, "human", "none", login)


def is_automated(comment: dict[str, Any]) -> bool:
    return classify(comment).automated
