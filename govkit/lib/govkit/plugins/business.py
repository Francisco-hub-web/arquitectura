"""Alineamiento de negocio (02.1-business-capability-alignment)."""
from __future__ import annotations

from govkit.paths import registry
from govkit.plugins import at, plugin
from govkit.plugins.structure import norm


@plugin("business.capability_registered", needs_dp=True)
def capability_registered(ctx, rule):
    cap = ctx.dp_get("spec.business.capability")
    if not cap:
        return
    reg = registry("capabilities")
    known = {norm(c) for c in reg.get("capabilities", [])}
    if norm(str(cap)) not in known:
        pending = reg.get("status") == "pendiente"
        yield at(ctx.dp, "spec.business.capability",
                 f"Capacidad `{cap}` no está en el mapa de capacidades registrado"
                 + (" (mapa pendiente de acuerdo con negocio: informativo)" if pending else ""),
                 severity="INFO" if pending else None)
