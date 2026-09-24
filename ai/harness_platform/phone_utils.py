import re


def normalize_phone(raw: str | None) -> str:
    """Normaliza telefone para dígitos (preferência E.164 sem +).

    Aceita chaves sintéticas quando o canal não envia telefone real:
    `cw{id}`, `tg{id}`, `conv{id}`, `id{slug}`.
    """
    if not raw:
        return ""
    text = str(raw).strip()
    if re.match(r"^(cw|tg|conv|id)[a-zA-Z0-9]+$", text):
        return text[:32]
    digits = re.sub(r"\D", "", text)
    if digits.startswith("00") and len(digits) > 4:
        digits = digits[2:]
    return digits


def normalize_whatsapp_phone(raw: str | None) -> str:
    """Normaliza para WhatsApp BR no formato 55xxxxxxxxxxx (só dígitos).

    - Remove máscara / + / espaços
    - Se vier DDI 55, mantém
    - Se vier só DDD+número (10/11 dígitos), prefixa 55
    - Ignora chaves sintéticas (cw/tg/…)
    """
    digits = normalize_phone(raw)
    if not digits:
        return ""
    if re.match(r"^(cw|tg|conv|id)", digits):
        return ""
    if digits.startswith("55") and len(digits) >= 12:
        return digits
    if digits.startswith("0"):
        digits = digits.lstrip("0")
    if len(digits) in (10, 11):
        return f"55{digits}"
    return digits
