"""Client-side fixed copy for CPR (form B).

`cpr/i18n/<locale>.yaml` holds dotted-key strings consumed by ``cpr/cli/render.py``
and the ``cpr`` entry. Locale resolution order matches form B 需求 §1 / agent1's
``cpr.cli.main._locale``:

    CPR_LOCALE > ~/.cpr/config client.locale > LANG > en-US

All keys MUST exist in both ``zh-CN.yaml`` and ``en-US.yaml`` to satisfy the
"双语对齐, 不留 fallback 缺口" 不通过条件 in the T-002b agent2 brief. The
loader still falls back to ``en-US`` and finally to the dotted key if the
caller asks for a key that no locale defines, so the caller never crashes.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

LOGGER = logging.getLogger(__name__)

_DEFAULT_LOCALE = "en-US"
_SUPPORTED = ("zh-CN", "en-US")
_DATA_DIR = Path(__file__).resolve().parent


def resolve_locale(
    config_locale: str | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """Pick the active locale.

    Order: ``CPR_LOCALE`` env var > config (``~/.cpr/config`` ``client.locale``,
    ignoring ``"auto"``) > ``LANG`` > ``en-US``. Anything other than zh-CN
    collapses to ``en-US`` (CPR ships only two locales in MVP).
    """
    values = env if env is not None else os.environ
    raw = values.get("CPR_LOCALE")
    if not raw and config_locale and config_locale != "auto":
        raw = config_locale
    if not raw:
        raw = values.get("LANG") or _DEFAULT_LOCALE
    normalized = raw.split(".", 1)[0].replace("_", "-")
    if normalized.startswith("zh"):
        return "zh-CN"
    return _DEFAULT_LOCALE


@lru_cache(maxsize=4)
def _load(locale: str) -> dict[str, Any]:
    path = _DATA_DIR / f"{locale}.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return _flatten(loaded) if isinstance(loaded, dict) else {}


def _flatten(node: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in node.items():
        full = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            out.update(_flatten(value, full))
        else:
            out[full] = value
    return out


class I18n:
    """Tiny string lookup with ``en-US`` fallback and ``{name}`` formatting.

    ``I18n("zh-CN").t("error.QUOTA_EXCEEDED.title", used=12, limit=50, hours=8)``
    pulls the zh-CN entry, falls back to en-US if missing, and finally returns
    the dotted key (after a warning) so callers never see KeyError.
    """

    def __init__(self, locale: str | None = None) -> None:
        self.locale = locale if locale in _SUPPORTED else _DEFAULT_LOCALE
        self._primary = _load(self.locale)
        self._fallback = _load(_DEFAULT_LOCALE) if self.locale != _DEFAULT_LOCALE else self._primary

    def t(self, key: str, /, **fmt: Any) -> str:
        value = self._primary.get(key)
        if value is None and self.locale != _DEFAULT_LOCALE:
            value = self._fallback.get(key)
            if value is not None:
                LOGGER.warning("missing i18n key %s for locale %s; fallback en-US", key, self.locale)
        if value is None:
            LOGGER.warning("missing i18n key %s for locale %s and en-US", key, self.locale)
            return key
        text = str(value)
        if fmt:
            try:
                return text.format(**fmt)
            except (KeyError, IndexError):
                LOGGER.warning("i18n format failed for key %s with %r", key, fmt)
                return text
        return text


__all__ = ["I18n", "resolve_locale"]
