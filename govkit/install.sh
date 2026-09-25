#!/usr/bin/env bash
# =============================================================================================
#  govkit — instalador (macOS / Linux · compatible con bash 3.2)
#  Uso:  cd ~/Downloads && tar xzf govkit-v1.tar.gz && cd govkit && ./install.sh && source ~/.zshrc
#  Opciones:
#    --pull-model        descarga el modelo local en Ollama (si Ollama está instalado)
#    --model NOMBRE      modelo por defecto (default: qwen2.5:7b-instruct)
#    --prefix RUTA       instalar en RUTA en vez de <lakehousev2>/governance/govkit
#    --no-rc             no modificar ~/.zshrc
#    --full-test         ejecutar la suite completa (≈20-30 s) además del smoke test
#  Variables: LAKEHOUSE_DIR=/ruta/a/lakehousev2  GOVKIT_PYTHON=/ruta/python3
# =============================================================================================
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(cat "$SRC/VERSION" 2>/dev/null || echo "0.0.0")"
MODEL="${GOVKIT_MODEL:-qwen2.5:7b-instruct}"
PULL_MODEL=0
NO_RC=0
FULL_TEST=0
PREFIX=""

say()  { printf "\033[1;36m▸\033[0m %s\n" "$*"; }
ok()   { printf "\033[1;32m✔\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m✘ %s\033[0m\n" "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --pull-model) PULL_MODEL=1 ;;
    --model) MODEL="${2:?--model requiere un valor}"; shift ;;
    --prefix) PREFIX="${2:?--prefix requiere una ruta}"; shift ;;
    --no-rc) NO_RC=1 ;;
    --full-test) FULL_TEST=1 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) die "Opción desconocida: $1 (usar --help)" ;;
  esac
  shift
done

printf "\n\033[1mgovkit %s · Sistema de Gobernanza Híbrido de Datos\033[0m\n\n" "$VERSION"

# ---------------------------------------------------------------------------------- 1. Python
find_python() {
  for c in "${GOVKIT_PYTHON:-}" /opt/homebrew/bin/python3 /usr/local/bin/python3 python3 /usr/bin/python3; do
    [ -z "$c" ] && continue
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
        command -v "$c"
        return 0
      fi
    fi
  done
  return 1
}
PY="$(find_python)" || die "Se requiere python3 >= 3.9 (macOS: xcode-select --install  o  brew install python)"
ok "Python: $PY ($("$PY" -c 'import platform; print(platform.python_version())'))"

# ---------------------------------------------------------------------------------- 2. lakehousev2
detect_lakehouse() {
  if [ -n "${LAKEHOUSE_DIR:-}" ]; then echo "$LAKEHOUSE_DIR"; return; fi
  for d in "$HOME/lakehousev2" "$HOME/Projects/lakehousev2" "$HOME/projects/lakehousev2" "$HOME/dev/lakehousev2" \
           "$HOME/Developer/lakehousev2" "$HOME/code/lakehousev2" "$HOME/repos/lakehousev2" "$HOME/git/lakehousev2" \
           "$HOME/src/lakehousev2" "$HOME/workspace/lakehousev2" "$HOME/Documents/lakehousev2" \
           "$HOME/Documents/GitHub/lakehousev2" "$HOME/Desktop/lakehousev2"; do
    if [ -d "$d" ]; then echo "$d"; return; fi
  done
  local found
  found="$(find "$HOME" -maxdepth 4 \( -path "$HOME/Library" -o -path "$HOME/.Trash" -o -name node_modules -o -name .git \
           -o -name .venv \) -prune -o -type d -name lakehousev2 -print 2>/dev/null | head -1 || true)"
  if [ -n "$found" ]; then echo "$found"; return; fi
  echo "$HOME/lakehousev2"
}

if [ -n "$PREFIX" ]; then
  TARGET="$PREFIX"
  LH="$(dirname "$(dirname "$PREFIX")")"
else
  LH="$(detect_lakehouse)"
  if [ ! -d "$LH" ]; then
    warn "No se encontró lakehousev2: se crea $LH (usa LAKEHOUSE_DIR=/ruta ./install.sh para otra ubicación)"
    mkdir -p "$LH"
  fi
  TARGET="$LH/governance/govkit"
fi
ok "lakehousev2: $LH"

# ---------------------------------------------------------------------------------- 3. Copia
if [ "$SRC" = "$TARGET" ]; then
  say "Ejecutando desde el directorio instalado: se omite la copia"
else
  if [ -e "$TARGET" ]; then
    BAK="$TARGET.bak-$(date +%Y%m%d%H%M%S)"
    mv "$TARGET" "$BAK"
    say "Versión previa respaldada en $BAK"
    ls -1d "$TARGET".bak-* 2>/dev/null | sort -r | tail -n +4 | while read -r old; do rm -rf "$old"; done
  fi
  mkdir -p "$(dirname "$TARGET")"
  cp -R "$SRC" "$TARGET"
  find "$TARGET" \( -name __pycache__ -o -name .DS_Store \) -prune -exec rm -rf {} + 2>/dev/null || true
fi
printf "%s\n" "$PY" > "$TARGET/.python"
chmod +x "$TARGET/bin/govkit" "$TARGET/install.sh" "$TARGET/uninstall.sh" 2>/dev/null || true
ok "Instalado en $TARGET"
if [ -d "$TARGET/docs" ]; then ok "Documentación de arquitectura: $TARGET/docs"; fi

# ---------------------------------------------------------------------------------- 4. Shell rc
write_block() {
  local rc="$1"
  local tmp
  tmp="$(mktemp "${TMPDIR:-/tmp}/govkit-rc.XXXXXX")"
  [ -f "$rc" ] || : > "$rc"
  cp "$rc" "$rc.govkit.bak"
  awk '/^# >>> govkit >>>/{skip=1} !skip{print} /^# <<< govkit <<</{skip=0}' "$rc" > "$tmp"
  cat >> "$tmp" <<EOF
# >>> govkit >>>
# Kit de Gobernanza Híbrida de Datos v$VERSION ($(date +%Y-%m-%d)) — bloque gestionado por govkit/install.sh
export GOVKIT_HOME="$TARGET"
export PATH="\$GOVKIT_HOME/bin:\$PATH"
export GOVKIT_MODEL="\${GOVKIT_MODEL:-$MODEL}"
alias gk='govkit'
alias gkl='govkit lint'
alias gkg='govkit gate --to listo_para_produccion'
alias gks='govkit score'
alias gkr='govkit review'
alias gka='govkit ask'
# <<< govkit <<<
EOF
  cat "$tmp" > "$rc"   # preserva symlinks de dotfiles
  rm -f "$tmp"
  ok "PATH y alias agregados a $rc (respaldo: $rc.govkit.bak)"
}
if [ "$NO_RC" -eq 0 ]; then
  write_block "$HOME/.zshrc"
  case "${SHELL:-}" in *bash) [ -f "$HOME/.bashrc" ] && write_block "$HOME/.bashrc" ;; esac
fi

# ---------------------------------------------------------------------------------- 5. Verificación
say "Verificando instalación…"
"$TARGET/bin/govkit" kb validate >/dev/null || die "La base de conocimiento no valida"
if "$TARGET/bin/govkit" lint "$TARGET/examples/sales-transactions-anl-dp-cl" --format json -o /dev/null 2>/dev/null; then
  ok "Smoke test: Data Product de referencia PASS · KB válida"
else
  die "Smoke test fallido: ejecuta $TARGET/bin/govkit lint $TARGET/examples/sales-transactions-anl-dp-cl"
fi
if [ "$FULL_TEST" -eq 1 ]; then
  say "Suite completa…"
  "$TARGET/bin/govkit" selftest || die "La suite de pruebas falló"
fi

# ---------------------------------------------------------------------------------- 6. Ollama (opcional)
if command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | awk 'NR>1{print $1}' | grep -qx "$MODEL"; then
    ok "Ollama: modelo $MODEL disponible"
  elif [ "$PULL_MODEL" -eq 1 ]; then
    say "Descargando $MODEL en Ollama…"
    ollama pull "$MODEL" && ok "Modelo $MODEL listo"
  else
    warn "Ollama instalado sin $MODEL → ollama pull $MODEL   (o ./install.sh --pull-model)"
  fi
else
  warn "Ollama no detectado (opcional, solo para revisión semántica): brew install ollama && ollama pull $MODEL"
fi

if [ -d "$LH/.git" ]; then
  say "lakehousev2 es un repo git. Hook opcional de pre-commit: govkit hooks install \"$LH\""
fi

cat <<EOF

$(printf "\033[1;32m")Listo.$(printf "\033[0m") Ejecuta:  source ~/.zshrc

  govkit doctor                                       # diagnóstico (Python, PyYAML, Ollama)
  govkit lint $TARGET/examples/sales-transactions-anl-dp-cl
  govkit init --domain sales --subdomain transactions --type anl --country cl --owner tu.email@cencosud.com
  govkit gate --to listo_para_produccion              # dentro de un repo de Data Product
  govkit kb route --task promover_a_produccion        # qué conocimiento carga el LLM
  govkit ask "¿qué exige el gate a producción?" --no-llm
  open $TARGET/docs/00-SAD-sistema-gobernanza-hibrido.md

EOF
