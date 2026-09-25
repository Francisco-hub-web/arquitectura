#!/usr/bin/env bash
# Construye dist/govkit-v<MAJOR>.tar.gz: kit + documentación de arquitectura, listo para ./install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(cat "$ROOT/govkit/VERSION")"
MAJOR="${VERSION%%.*}"
OUT="$ROOT/dist/govkit-v${MAJOR}.tar.gz"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp -R "$ROOT/govkit" "$STAGE/govkit"
rm -rf "$STAGE/govkit/docs"
cp -R "$ROOT/docs" "$STAGE/govkit/docs"
find "$STAGE/govkit" \( -name __pycache__ -o -name .DS_Store -o -name '*.pyc' -o -name .python \) -prune -exec rm -rf {} +
chmod +x "$STAGE/govkit/install.sh" "$STAGE/govkit/uninstall.sh" "$STAGE/govkit/bin/govkit"

# Reproducibilidad: regenerar la matriz desde el catálogo y validar antes de empaquetar
"$STAGE/govkit/bin/govkit" rules --format md > "$STAGE/govkit/docs/01-matriz-reglas.md"
"$STAGE/govkit/bin/govkit" kb validate >/dev/null
"$STAGE/govkit/bin/govkit" lint "$STAGE/govkit/examples/sales-transactions-anl-dp-cl" --format json -o /dev/null
find "$STAGE/govkit" \( -name __pycache__ -o -name .python \) -prune -exec rm -rf {} +

mkdir -p "$ROOT/dist"
tar --owner=0 --group=0 --numeric-owner -C "$STAGE" -czf "$OUT" govkit 2>/dev/null || tar -C "$STAGE" -czf "$OUT" govkit
echo "✔ $OUT ($(du -h "$OUT" | cut -f1)) · govkit $VERSION"
echo "  Instalar: cd ~/Downloads && tar xzf $(basename "$OUT") && cd govkit && ./install.sh && source ~/.zshrc"
