#!/usr/bin/env python3
"""
Compuerta `esquema` — compara el esquema real de una tabla contra su contrato.

Es la compuerta que atrapa el fallo característico de una plataforma de datos:
una tabla que tiene la cantidad de filas correcta y le faltan columnas.

Uso
---
  # Solo sintaxis del contrato (compuerta `contrato`, cierre de DISENO)
  python verificar_contrato.py contratos/core.dim_fecha.yml --solo-sintaxis

  # Comparacion real (compuerta `esquema`, cierre de VALIDACION)
  python verificar_contrato.py contratos/core.dim_fecha.yml --esquema esquema.json

El archivo de esquema lo produce el agente contra el tenant. Snippet:

    import json, datetime
    df = spark.table("core.dim_fecha")
    print(json.dumps({
        "tabla": "core.dim_fecha",
        "medido_en": datetime.datetime.utcnow().isoformat() + "Z",
        "filas": df.count(),
        "columnas": [{"nombre": c.name, "tipo": c.dataType.simpleString(),
                      "nulable": c.nullable} for c in df.schema.fields],
    }, indent=2))

Honestidad sobre la fuerza de esta compuerta: la *comparacion* es de maquina y no
se puede falsear. El *snapshot* de esquema es un recibo — lo produce el agente.
Lo que se gana es que el agente ya no puede decir "validado" mirando el conteo de
filas: tiene que producir el esquema entero y el script lo confronta columna por
columna.

Salida: 0 si pasa, 1 si falla, 2 si el contrato o el snapshot estan mal formados.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: falta pyyaml.  pip install pyyaml", file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import recibos  # noqa: E402


CAMPOS_OBLIGATORIOS = ["tabla", "capa", "grano", "clave_natural", "columnas"]
CAMPOS_COLUMNA = ["nombre", "tipo", "nulable"]

# Sinonimos aceptados entre lo declarado y lo que devuelve Spark.
EQUIVALENTES = {
    "int": {"int", "integer"},
    "bigint": {"bigint", "long"},
    "string": {"string", "varchar", "str"},
    "double": {"double", "float64"},
    "boolean": {"boolean", "bool"},
    "date": {"date"},
    "timestamp": {"timestamp"},
}


def _normalizar(tipo: str) -> str:
    t = (tipo or "").strip().lower()
    for canonico, alias in EQUIVALENTES.items():
        if t in alias:
            return canonico
    return t  # decimal(18,2) y demas quedan como vinieron


class Resultado:
    def __init__(self) -> None:
        self.errores: list[str] = []
        self.avisos: list[str] = []

    def error(self, msg: str) -> None:
        self.errores.append(msg)

    def aviso(self, msg: str) -> None:
        self.avisos.append(msg)

    @property
    def paso(self) -> bool:
        return not self.errores

    def informar(self, titulo: str) -> None:
        print(f"\n=== {titulo} ===")
        for a in self.avisos:
            print(f"  [aviso] {a}")
        for e in self.errores:
            print(f"  [ERROR] {e}")
        print(f"\n  {'PASA' if self.paso else 'FALLA'}"
              f"  ({len(self.errores)} errores, {len(self.avisos)} avisos)\n")


def validar_sintaxis(contrato: dict, r: Resultado) -> None:
    for campo in CAMPOS_OBLIGATORIOS:
        if campo not in contrato or contrato[campo] in (None, "", []):
            r.error(f"falta el campo obligatorio '{campo}'")

    grano = contrato.get("grano", "")
    if grano and not grano.strip().lower().startswith("una fila por"):
        r.aviso("el grano no empieza con 'una fila por' — conviene esa forma, "
                "obliga a decidirlo explicitamente")

    columnas = contrato.get("columnas") or []
    if not isinstance(columnas, list):
        r.error("'columnas' tiene que ser una lista")
        return

    vistas: set[str] = set()
    for i, col in enumerate(columnas):
        if not isinstance(col, dict):
            r.error(f"columna #{i}: tiene que ser un mapa")
            continue
        for campo in CAMPOS_COLUMNA:
            if campo not in col:
                r.error(f"columna '{col.get('nombre', f'#{i}')}': falta '{campo}'")
        nombre = col.get("nombre")
        if nombre in vistas:
            r.error(f"columna '{nombre}' declarada dos veces")
        vistas.add(nombre)

    # La clave natural tiene que existir entre las columnas declaradas.
    for k in contrato.get("clave_natural") or []:
        if k not in vistas:
            r.error(f"la clave natural incluye '{k}', que no esta entre las columnas")

    # Una clave natural nulable es una contradiccion.
    por_nombre = {c.get("nombre"): c for c in columnas if isinstance(c, dict)}
    for k in contrato.get("clave_natural") or []:
        col = por_nombre.get(k)
        if col and col.get("nulable") is True:
            r.error(f"'{k}' es clave natural y esta declarada nulable")

    # Una regla de unicidad sobre la clave natural deberia existir.
    reglas = contrato.get("calidad") or []
    tiene_unicidad = any(x.get("regla") == "unicidad" for x in reglas if isinstance(x, dict))
    if not tiene_unicidad:
        r.aviso("no hay regla de calidad 'unicidad' — sin ella nada verifica el grano")


def comparar_esquema(contrato: dict, snap: dict, r: Resultado) -> None:
    tabla_c = contrato.get("tabla")
    tabla_s = snap.get("tabla")
    if tabla_c != tabla_s:
        r.error(f"el snapshot es de '{tabla_s}' y el contrato de '{tabla_c}'")
        return

    if "medido_en" not in snap:
        r.aviso("el snapshot no dice cuando se midio")

    declaradas = {c["nombre"]: c for c in contrato["columnas"]}
    reales = {c["nombre"]: c for c in snap.get("columnas", [])}

    faltan = [n for n in declaradas if n not in reales]
    sobran = [n for n in reales if n not in declaradas]

    for n in faltan:
        r.error(f"columna declarada y ausente en la tabla: '{n}'")
    for n in sobran:
        r.error(f"columna en la tabla y no declarada en el contrato: '{n}'")

    for n, dec in declaradas.items():
        real = reales.get(n)
        if not real:
            continue
        t_dec, t_real = _normalizar(dec["tipo"]), _normalizar(real["tipo"])
        if t_dec != t_real:
            r.error(f"'{n}': tipo declarado '{dec['tipo']}', real '{real['tipo']}'")
        # Una columna declarada NOT NULL que en la tabla admite nulos es un riesgo
        # real: es exactamente como una FK termina nula sin que nadie se entere.
        if dec.get("nulable") is False and real.get("nulable") is True:
            r.aviso(f"'{n}': declarada no nulable, la tabla la admite nula "
                    f"(Delta no impone NOT NULL — verificar con una regla de calidad)")

    print(f"  columnas declaradas: {len(declaradas)}   en la tabla: {len(reales)}")
    if "filas" in snap:
        print(f"  filas: {snap['filas']}")

    for regla in contrato.get("calidad") or []:
        if not isinstance(regla, dict):
            continue
        if regla.get("regla") == "filas" and "filas" in snap:
            n = snap["filas"]
            lo, hi = regla.get("minimo"), regla.get("maximo")
            if lo is not None and n < lo:
                r.error(f"filas={n}, por debajo del minimo declarado ({lo})")
            if hi is not None and n > hi:
                r.error(f"filas={n}, por encima del maximo declarado ({hi})")


def main() -> int:
    p = argparse.ArgumentParser(description="Compuerta de esquema de FAW")
    p.add_argument("contrato", type=Path)
    p.add_argument("--esquema", type=Path,
                   help="JSON con el esquema real medido contra el tenant")
    p.add_argument("--solo-sintaxis", action="store_true")
    args = p.parse_args()

    if not args.contrato.exists():
        print(f"ERROR: no existe {args.contrato}", file=sys.stderr)
        return 2

    try:
        contrato = yaml.safe_load(args.contrato.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"ERROR: el contrato no es YAML valido: {e}", file=sys.stderr)
        return 2

    r = Resultado()
    validar_sintaxis(contrato, r)

    # El recibo se emite por tabla (ambito): un ticket puede tocar varias y con
    # un archivo unico cada corrida pisaba a la anterior — la compuerta cerraba
    # DISENO probando solo la ultima tabla verificada.
    tabla = contrato.get("tabla") if isinstance(contrato, dict) else None

    if args.solo_sintaxis:
        r.informar(f"Sintaxis — {args.contrato.name}")
        if r.paso:
            recibos.emitir("contrato", "verificar_contrato.py --solo-sintaxis",
                           [args.contrato],
                           f"{tabla}: {len(contrato.get('columnas') or [])} columnas "
                           f"declaradas, grano y clave presentes",
                           ambito=tabla)
        else:
            recibos.invalidar("contrato", ambito=tabla)
        return 0 if r.paso else 1

    if not args.esquema:
        print("ERROR: hace falta --esquema, o --solo-sintaxis.\n"
              "       Sin el esquema real no hay nada que comparar, y una compuerta\n"
              "       que se salta cuando falta el insumo no es una compuerta.",
              file=sys.stderr)
        return 2

    if not args.esquema.exists():
        print(f"ERROR: no existe {args.esquema}", file=sys.stderr)
        return 2

    try:
        snap = json.loads(args.esquema.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: el snapshot no es JSON valido: {e}", file=sys.stderr)
        return 2

    if r.paso:
        comparar_esquema(contrato, snap, r)

    r.informar(f"Esquema — {contrato.get('tabla')}")
    if r.paso:
        recibos.emitir("esquema", "verificar_contrato.py",
                       [args.contrato, args.esquema],
                       f"{contrato.get('tabla')}: {len(contrato['columnas'])} columnas "
                       f"coinciden, {snap.get('filas', '?')} filas",
                       ambito=tabla)
    else:
        recibos.invalidar("esquema", ambito=tabla)
    return 0 if r.paso else 1


if __name__ == "__main__":
    sys.exit(main())
