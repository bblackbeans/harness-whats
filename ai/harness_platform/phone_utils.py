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
