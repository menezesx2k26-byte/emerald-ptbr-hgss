from __future__ import annotations

import os
import re


DEFAULT_RELEASE_VERSION = "1.3.1"
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")


def release_version() -> str:
    value = os.environ.get("EMERALD_RELEASE_VERSION", DEFAULT_RELEASE_VERSION)
    if not VERSION_RE.fullmatch(value):
        raise ValueError(f"Invalid EMERALD_RELEASE_VERSION: {value!r}")
    return value


def release_tag() -> str:
    return f"v{release_version()}"
