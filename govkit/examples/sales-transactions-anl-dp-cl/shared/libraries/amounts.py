"""Utilidades compartidas entre jobs del producto (no entre productos: shared/ es interno)."""


def net_amount(gross: float, discount: float) -> float:
    return round((gross or 0.0) - (discount or 0.0), 2)
