from __future__ import annotations

import re
from dataclasses import dataclass


VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
ALLOWED_VARIABLES = {"name", "email", "phone", "page_name", "form_name"}


@dataclass
class RenderContext:
    name: str = ""
    email: str = ""
    phone: str = ""
    page_name: str = ""
    form_name: str = ""


def render_template(template: str, context: dict[str, str]) -> str:
    def replacement(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in ALLOWED_VARIABLES:
            return ""
        return context.get(key, "")

    return VARIABLE_PATTERN.sub(replacement, template)
