#!/usr/bin/env bash
# govkit — desinstalador: quita el bloque de ~/.zshrc (y ~/.bashrc) y elimina GOVKIT_HOME.
#   ./uninstall.sh [-y]
set -euo pipefail
HOME_DIR="${GOVKIT_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
YES=0
[ "${1:-}" = "-y" ] && YES=1

for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
  if [ -f "$rc" ] && grep -q "^# >>> govkit >>>" "$rc"; then
    tmp="$(mktemp "${TMPDIR:-/tmp}/govkit-rc.XXXXXX")"
    awk '/^# >>> govkit >>>/{skip=1} !skip{print} /^# <<< govkit <<</{skip=0}' "$rc" > "$tmp"
    cat "$tmp" > "$rc"
    rm -f "$tmp"
    echo "✔ Bloque govkit eliminado de $rc"
  fi
done

if [ "$YES" -eq 0 ]; then
  printf "¿Eliminar %s? [s/N] " "$HOME_DIR"
  read -r ans
  case "$ans" in s|S|y|Y) ;; *) echo "Se conserva $HOME_DIR"; exit 0 ;; esac
fi
rm -rf "$HOME_DIR"
echo "✔ govkit eliminado. Abre una nueva terminal o ejecuta: source ~/.zshrc"
