#!/usr/bin/env python3
"""
Hook PreToolUse (Bash|PowerShell) — corre el checklist de `cliente.md` sobre el
cuerpo de un PR ANTES de que el PR exista.

## Por que existe

Una regla escrita en `cliente.md` no alcanza si nada la aplica en el momento de
escribir: el cuerpo de un PR en un repo de cliente tiende a crecer con
razonamiento de diseno, hallazgos de negocio abiertos y cifras que le generan
preguntas al cliente, aunque la regla diga explicitamente que eso no va ahi.
Esta compuerta corre antes de que el PR exista, no depende de que se la recuerde.

FAW no distingue repos propios de repos de cliente: el cuerpo de un PR se
escribe siempre como si lo leyera el destinatario del repo.

## Lo que revisa

1. Largo: mas de LIMITE_TEXTO lineas de texto es demasiado. Tablas, bullets y
   bloques de codigo NO cuentan — la ficha tecnica se agradece; los parrafos de
   razonamiento son el problema.
2. Atribucion de IA: prohibida sin excepcion.
3. Metodologia interna y nombres de otros clientes o repos internos.
4. Secciones que el usuario marco como de mas: "Validacion", "Despliegue".
5. Hablar del cliente en tercera persona ("el cliente", "llevar al cliente"),
   y asignar tareas a gente del cliente.

Opt-in: solo actua si el proyecto tiene `.faw/`, y solo sobre los comandos que
crean o editan un PR (`gh pr create|edit`, `az repos pr create|update`).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import superficie  # noqa: E402

LIMITE_TEXTO = 8

# Los dos clientes de linea de comandos que crean o editan un PR. Cubrir solo
# uno dejaba la compuerta sin efecto en cualquier proyecto que usara el otro,
# y sin ningun aviso: la compuerta no se salteaba, directamente no existia.
RE_PR = re.compile(r"\bgh\s+pr\s+(create|edit)\b"
                   r"|\baz\s+repos\s+pr\s+(create|update)\b")

# Solo aplica al cuerpo de un PR, no a los archivos: un notebook si puede
# documentar como se valido. Por eso vive aca y no en superficie.py.
RE_SECCION_DE_MAS = re.compile(r"^#+\s*(validaci|despliegue|deployment)",
                               re.IGNORECASE | re.MULTILINE)

# Los patrones viven en superficie.py: los comparte con la compuerta de commit.
# Tenerlos duplicados fue parte del problema — se revisaba el cuerpo del PR con
# una lista y los archivos con ninguna.


def _body(comando: str, repo: Path) -> str | None:
    """
    Extrae el cuerpo del PR del comando. Cubre `--body 'x'`, `--body "x"`,
    `--body=x`, el heredoc de `--body-file -` y `--body-file <ruta>`.

    Devolver None para `--body-file` apaga la compuerta en silencio: un PR creado
    con `--body-file - <<'EOF'` no se revisaria nunca, aunque el mismo contenido
    con `--body "..."` si se bloquee. El cuerpo del heredoc SI esta en el string
    del comando; solo hay que leerlo.
    """
    for rx in (
        r"--body\s*=\s*'((?:[^'\\]|\\.)*)'",
        r'--body\s*=\s*"((?:[^"\\]|\\.)*)"',
        r"--body\s+'((?:[^'\\]|\\.)*)'",
        r'--body\s+"((?:[^"\\]|\\.)*)"',
    ):
        m = re.search(rx, comando, re.DOTALL)
        if m:
            return m.group(1)

    # --body-file - <<'EOF' ... EOF   (o <<EOF, o cualquier delimitador)
    m = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*\n(.*?)\n\1\s*$",
                  comando, re.DOTALL | re.MULTILINE)
    if m:
        return m.group(2)

    # --body-file <ruta>
    m = re.search(r"--body-file[\s=]+(?!-\s)(['\"]?)([^\s'\"]+)\1", comando)
    if m:
        ruta = Path(m.group(2))
        if not ruta.is_absolute():
            ruta = repo / ruta
        try:
            return ruta.read_text(encoding="utf-8-sig")
        except OSError:
            return None

    return None


def _lineas_texto(cuerpo: str) -> int:
    """Cuenta solo texto corrido: ignora titulos, tablas, bullets, codigo y vacias."""
    n = 0
    en_codigo = False
    for linea in cuerpo.splitlines():
        s = linea.strip()
        if s.startswith("```"):
            en_codigo = not en_codigo
            continue
        if en_codigo or not s:
            continue
        if s.startswith("#") or s.startswith("|") or s.startswith(("-", "*", ">")):
            continue
        if re.match(r"^\d+[\.\)]\s", s):
            continue
        n += 1
    return n


def _denegar(motivo: str) -> int:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motivo,
        }
    }, ensure_ascii=False))
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    try:
        entrada = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return 0

    repo = Path(entrada.get("cwd") or ".")
    if not (repo / ".faw").is_dir():
        return 0

    comando = (entrada.get("tool_input") or {}).get("command", "") or ""
    if not RE_PR.search(comando):
        return 0

    cuerpo = _body(comando, repo)
    if cuerpo is None:
        # Sigue habiendo formas de pasar el cuerpo que no se pueden leer del
        # comando (una variable, un pipe). Ahi se avisa en vez de bloquear, pero
        # el commit ya paso por la compuerta de superficie sobre los archivos:
        # esto no es la unica linea de defensa como antes.
        print("[faw] No pude leer el cuerpo de este PR para chequear cliente.md. "
              "Revisar a mano: max ~8 lineas de texto, sin atribucion de IA, sin "
              "metodologia interna, sin secciones de Validacion/Despliegue, sin "
              "hablar del cliente en tercera persona.", file=sys.stderr)
        return 0

    fallos: list[str] = []

    n = _lineas_texto(cuerpo)
    if n > LIMITE_TEXTO:
        fallos.append(f"{n} lineas de texto (max {LIMITE_TEXTO}). Tablas y bullets no cuentan: "
                      f"la ficha tecnica se agradece, los parrafos de razonamiento sobran.")

    for motivo, fragmento in superficie.revisar(cuerpo, repo):
        fallos.append(f"{motivo}  -> \"{fragmento[:60]}\"")

    m_seccion = RE_SECCION_DE_MAS.search(cuerpo)
    if m_seccion:
        fallos.append("seccion 'Validacion' o 'Despliegue' — que se valido se da por supuesto, "
                      f"y los pasos de despliegue los ejecuta el usuario  -> \"{m_seccion.group(0)[:60]}\"")

    if not fallos:
        return 0

    return _denegar(
        "FAW: PR bloqueado por el checklist de superficie de cliente (reglas/cliente.md).\n"
        "Todo repo gobernado por FAW se trata como superficie de cliente: lo que se "
        "escribe aca lo lee el destinatario del repo.\n\n"
        + "\n".join(f"  - {f}" for f in fallos)
        + "\n\nEl cuerpo que funciona: una oracion de que es y para que, tabla de origen de datos,\n"
          "contenido en bullets, y una linea de fundamento solo si el revisor la necesita.\n"
          "El razonamiento largo va en el mensaje del commit. Los hallazgos de negocio, a la minuta."
    )


if __name__ == "__main__":
    sys.exit(main())
