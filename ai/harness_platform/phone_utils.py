import re


def normalize_phone(raw: str | None) -> str:
    """Normaliza telefone para dígitos (preferência E.164 sem +)."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("00") and len(digits) > 4:
        digits = digits[2:]
    return digits
