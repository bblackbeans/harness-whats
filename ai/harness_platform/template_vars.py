import json
import re
from typing import Any

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")
_SIMPLE_RE = re.compile(r"\{([a-zA-Z0-9_.-]+)\}")


def profile_variables(profile: dict[str, Any] | None) -> dict[str, Any]:
    """Monta dict plano de variáveis a partir do perfil do contato."""
    if not profile:
        return {}
    vars_: dict[str, Any] = {
        "phone": profile.get("phone") or "",
        "telefone": profile.get("phone") or "",
        "nome": profile.get("name") or "",
        "name": profile.get("name") or "",
        "email": profile.get("email") or "",
    }
    fields = profile.get("fields") or {}
    if isinstance(fields, dict):
        for key, value in fields.items():
            vars_[str(key)] = value
    return vars_


def render_template(template: str, variables: dict[str, Any]) -> str:
    """Substitui {{campo}} e {campo} pelos valores do dict."""
    if not template:
        return ""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            return match.group(0)
        value = variables[key]
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return "" if value is None else str(value)

    out = _VAR_RE.sub(_replace, template)
    out = _SIMPLE_RE.sub(_replace, out)
    return out


def get_by_path(data: Any, path: str) -> Any:
    """Resolve path tipo lead.name ou lead[0].email."""
    if not path:
        return None
    current = data
    for part in path.replace("[", ".").replace("]", "").split("."):
        if not part:
            continue
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if 0 <= idx < len(current) else None
        else:
            return None
    return current


def apply_field_mapping(payload: dict, mapping: dict[str, str]) -> dict[str, Any]:
    """Mapeia paths JSON → chaves de campo (ex.: lead.email → email)."""
    result: dict[str, Any] = {}
    for target_key, source_path in (mapping or {}).items():
        if not target_key or not source_path:
            continue
        value = get_by_path(payload, str(source_path))
        if value is not None:
            result[str(target_key)] = value
    return result
