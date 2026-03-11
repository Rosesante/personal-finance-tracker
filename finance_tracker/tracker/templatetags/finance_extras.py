from django import template

register = template.Library()


@register.filter
def money(value, currency: str = "TZS"):
    if value is None:
        value = 0
    symbol = _currency_symbol(currency)
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return f"{symbol}{value}"
    return f"{symbol}{amount:,.2f}"


def _currency_symbol(code: str) -> str:
    if not code:
        return "TSh "
    code = code.upper()
    if code == "TZS":
        return "TSh "
    if code == "USD":
        return "$"
    if code == "EUR":
        return "€"
    if code == "GBP":
        return "£"
    return f"{code} "
