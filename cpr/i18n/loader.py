from __future__ import annotations

import logging
import os

LOGGER = logging.getLogger(__name__)

MESSAGES = {
    "zh-CN": {
        "app.name": "CPR 命令工作台",
        "slash.help": "/ai /explain /fix /help /clear /back",
    },
    "en-US": {
        "app.name": "CPR Command Workspace",
        "slash.help": "/ai /explain /fix /help /clear /back",
    },
}


def resolve_locale(config_locale: str | None = None, env: dict[str, str] | None = None) -> str:
    values = env or os.environ
    raw = values.get("CPR_LOCALE") or config_locale or values.get("LANG") or "en-US"
    normalized = raw.split(".", 1)[0].replace("_", "-")
    if normalized.startswith("zh-CN"):
        return "zh-CN"
    if normalized.startswith("en"):
        return "en-US"
    return normalized if normalized in MESSAGES else "en-US"


class I18nLoader:
    def __init__(self, locale: str | None = None) -> None:
        self.locale = locale or resolve_locale()

    def text(self, key: str) -> str:
        current = MESSAGES.get(self.locale, {})
        if key in current:
            return current[key]
        fallback = MESSAGES.get("en-US", {})
        if key in fallback:
            LOGGER.warning("missing i18n key %s for locale %s; fallback en-US", key, self.locale)
            return fallback[key]
        LOGGER.warning("missing i18n key %s for locale %s", key, self.locale)
        return key

    def node_text(self, values: dict[str, str], node_id: str) -> str:
        if self.locale in values:
            return values[self.locale]
        if "en-US" in values:
            LOGGER.warning("missing node text for %s locale %s; fallback en-US", node_id, self.locale)
            return values["en-US"]
        if "zh-CN" in values:
            LOGGER.warning("missing node text for %s locale %s; fallback zh-CN", node_id, self.locale)
            return values["zh-CN"]
        LOGGER.warning("missing node text for %s", node_id)
        return node_id
