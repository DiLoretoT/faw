#!/usr/bin/env python3
"""
Compuerta `modelo` — compara la definicion real de un modelo semantico contra
lo declarado.

El dialogo de "nueva relacion" en Power BI Desktop viene con una columna
preseleccionada, y aceptarla sin mirar deja relaciones de distintos roles de
fecha (o de cualquier otro rol que se repita) apuntando a la misma columna del
fact. El resultado filtra por el rol equivocado sin ningun error ni warning:
totales plausibles y equivocados.

El diagrama del modelo dibuja una linea entre dos tablas; no muestra a que
columna llega. El error es invisible en la vista que uno mira para revisarlo.
Por eso esto se verifica leyendo la definicion, no mirando la pantalla.

Uso
---
  python verificar_modelo.py modelo.esperado.yml --definicion model.bim.json

La definicion se obtiene con el MCP de Fabric (get_semantic_model_definition,
formato TMSL) y decodificando el payload base64 de la parte 'model.bim'.

Salida: 0 si pasa, 1 si falla, 2 si algun archivo esta mal formado.
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


# Conector Power Query segun el sabor de Direct Lake. Sirve para verificar que
# el modelo salio en el modo que se decidio y no en el default del boton.
CONECTOR_POR_MODO = {
    "directlake_onelake": "AzureStorage.DataLake",
    "directlake_sql": "Sql.Database",
}


class Resultado:
    def __init__(self) -> None:
        self.errores: list[str] = []
        self.avisos: list[str] = []

    def error(self, m: str) -> None:
        self.errores.append(m)

    def aviso(self, m: str) -> None:
        self.avisos.append(m)

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


def _rel_str(r: dict) -> str:
    return (f"{r.get('fromTable')}[{r.get('fromColumn')}] -> "
            f"{r.get('toTable')}[{r.get('toColumn')}]")


def verificar(esp: dict, modelo: dict, r: Resultado) -> None:
    m = modelo.get("model", modelo)
    tablas = {t["name"]: t for t in m.get("tables", [])}

    # --- Tablas ---
    esperadas = set(esp.get("tablas") or [])
    reales = set(tablas)
    for t in sorted(esperadas - reales):
        r.error(f"tabla declarada y ausente del modelo: '{t}'")
    for t in sorted(reales - esperadas):
        r.error(f"tabla en el modelo y no declarada: '{t}'")
    print(f"  tablas: {len(reales)}")

    # --- Modo de almacenamiento ---
    modo = (esp.get("modo") or "").strip().lower()
    if modo in CONECTOR_POR_MODO:
        esperado = CONECTOR_POR_MODO[modo]
        expresiones = json.dumps(m.get("expressions", []))
        if esperado not in expresiones:
            otros = [c for k, c in CONECTOR_POR_MODO.items() if k != modo]
            encontrado = next((c for c in otros if c in expresiones), "ninguno conocido")
            r.error(f"modo declarado '{modo}' (conector {esperado}), "
                    f"pero en el modelo aparece: {encontrado}")
        else:
            print(f"  modo: {modo} (conector {esperado}) OK")

    # --- Relaciones: la parte que importa ---
    reales_rel = m.get("relationships", []) or []
    print(f"  relaciones: {len(reales_rel)}")

    pendientes = list(reales_rel)
    for e in esp.get("relaciones") or []:
        buscada = None
        for cand in pendientes:
            if (cand.get("fromTable") == e["desde_tabla"]
                    and cand.get("fromColumn") == e["desde_columna"]
                    and cand.get("toTable") == e["hacia_tabla"]
                    and cand.get("toColumn") == e["hacia_columna"]):
                buscada = cand
                break
        if not buscada:
            r.error("relacion declarada y ausente: "
                    f"{e['desde_tabla']}[{e['desde_columna']}] -> "
                    f"{e['hacia_tabla']}[{e['hacia_columna']}]")
            continue
        pendientes.remove(buscada)

        # isActive ausente en TMSL significa activa.
        activa = buscada.get("isActive", True)
        if e.get("activa", True) != activa:
            r.error(f"{_rel_str(buscada)}: activa={activa}, "
                    f"declarada activa={e.get('activa', True)}")

    for extra in pendientes:
        r.error(f"relacion en el modelo y no declarada: {_rel_str(extra)}")

    # Dos relaciones distintas apuntando a la misma columna destino es el patron
    # exacto que este verificador esta pensado para atrapar. Puede ser legitimo,
    # pero nunca deberia pasar sin que alguien lo haya mirado.
    destinos: dict[str, list[str]] = {}
    for rel in reales_rel:
        clave = f"{rel.get('toTable')}[{rel.get('toColumn')}]"
        destinos.setdefault(clave, []).append(_rel_str(rel))
    for clave, lista in destinos.items():
        if len(lista) > 1:
            r.aviso(f"{len(lista)} relaciones apuntan a {clave} — "
                    f"revisar que no sea la columna preseleccionada del dialogo:\n"
                    + "".join(f"           {x}\n" for x in lista))

    # --- Propiedades de columna ---
    for pc in esp.get("columnas") or []:
        t = tablas.get(pc["tabla"])
        if not t:
            continue
        col = next((c for c in t.get("columns", []) if c["name"] == pc["columna"]), None)
        if not col:
            r.error(f"{pc['tabla']}[{pc['columna']}]: no existe en el modelo")
            continue
        if "sumarizar" in pc:
            real = col.get("summarizeBy", "default")
            if real != pc["sumarizar"]:
                r.error(f"{pc['tabla']}[{pc['columna']}]: summarizeBy='{real}', "
                        f"declarado '{pc['sumarizar']}'")
        if "ordenar_por" in pc:
            real = col.get("sortByColumn")
            if real != pc["ordenar_por"]:
                r.error(f"{pc['tabla']}[{pc['columna']}]: sortByColumn='{real}', "
                        f"declarado '{pc['ordenar_por']}'")

    # --- Medidas ---
    esperadas_med = set(esp.get("medidas") or [])
    if esperadas_med:
        reales_med = {med["name"] for t in tablas.values() for med in t.get("measures", [])}
        for x in sorted(esperadas_med - reales_med):
            r.error(f"medida declarada y ausente: '{x}'")
        print(f"  medidas: {len(reales_med)}")


def main() -> int:
    p = argparse.ArgumentParser(description="Compuerta de modelo semantico de FAW")
    p.add_argument("esperado", type=Path, help="YAML con lo declarado en DISENO")
    p.add_argument("--definicion", type=Path, required=True,
                   help="model.bim decodificado (JSON)")
    args = p.parse_args()

    for f in (args.esperado, args.definicion):
        if not f.exists():
            print(f"ERROR: no existe {f}", file=sys.stderr)
            return 2

    try:
        esp = yaml.safe_load(args.esperado.read_text(encoding="utf-8"))
        modelo = json.loads(args.definicion.read_text(encoding="utf-8"))
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        print(f"ERROR: archivo mal formado: {e}", file=sys.stderr)
        return 2

    r = Resultado()
    verificar(esp, modelo, r)
    r.informar(f"Modelo — {esp.get('modelo', args.esperado.stem)}")
    if r.paso:
        recibos.emitir("modelo", "verificar_modelo.py",
                       [args.esperado, args.definicion],
                       f"{esp.get('modelo')}: {len(esp.get('relaciones') or [])} relaciones "
                       f"y modo '{esp.get('modo')}' verificados")
    else:
        recibos.invalidar("modelo")
    return 0 if r.paso else 1


if __name__ == "__main__":
    sys.exit(main())
