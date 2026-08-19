---
name: faw-perfilar
description: Fase de perfilado de FAW. Mide el origen contra datos reales y produce el recibo con las consultas que respaldan cada número. Usar antes de diseñar cualquier artefacto de datos.
---

# Perfilar

Fase 2 de FAW. **Nada de diseño hasta que haya números.**

En software los requisitos vienen de personas. En datos, la mitad están en el origen y solo se descubren midiendo. Cada pregunta contestada por asunción produce un artefacto que funciona y da mal.

## Regla que gobierna esta fase

**Cada número va con la consulta que lo produjo.** Un número sin consulta no entra al recibo.

Perfilar es solo lectura. Si hace falta escribir algo, pedí autorización explícita primero.

## Qué medís

### Origen nuevo

```python
# Filas
df.count()

# Clave natural candidata — lo que decide si es clave o no
total = df.count()
unicos = df.select(*CLAVE).distinct().count()
print(f"filas={total}  unicos={unicos}  duplicados={total - unicos}")

# Por cada columna que Gold va a consumir
df.select([
    F.count(F.when(F.col(c).isNull(), c)).alias(f"{c}_nulos") for c in COLS
]).show()

# Centinelas del origen, con su porcentaje real
for c in COLS_FECHA:
    df.select(F.round(100 * F.avg((F.col(c) == LIT_CENTINELA).cast("int")), 2)).show()

# Tipos reales, no los de la ficha
df.printSchema()
```

**La clave natural se prueba, no se copia de una ficha.** Lo que documenta un origen y lo que el origen es divergen con el tiempo: una ficha puede nombrar una columna que la tabla ya no tiene, o que nunca tuvo. La clave se confirma consultando la tabla.

### Gold existente (tiers `MODELO` y `REPORTE`)

- Filas y columnas de cada tabla que el modelo va a consumir.
- Los totales de negocio que el reporte debería reproducir.
- Distribución de las dimensiones sobre las que se va a segmentar.

### Síntoma (tier `INCIDENTE`)

Qué se esperaba, qué se obtuvo, desde cuándo. Historial del artefacto: última escritura, último cambio de esquema (`DESCRIBE HISTORY`).

El apuro no exime de medir: el diagnóstico se mide, no se supone.

## Qué producís

`docs/faw/<ticket>/perfilado.md`:

```markdown
# Perfilado — <entidad>
Medido el <fecha> contra <ambiente>.

## Volumen
| Métrica | Valor | Consulta |
|---|---:|---|

## Clave natural
Candidata: `[...]` — filas N, únicos N, duplicados 0.
<consulta>

## Columnas
| Columna | Tipo | Nulos | Distinct | Notas |
|---|---|---:|---:|---|

## Hallazgos
1. ...

## Preguntas que quedan abiertas
- ... (para el negocio, con quién debería responderlas)
```

## Cierre

```bash
python <faw>/scripts/estado.py mover --a DISENO --compuerta perfil=docs/faw/<ticket>/perfilado.md
```

## Trampas

- **Reportar un número sin haberlo medido.** Si no lo mediste, escribí "no medido".
- **Perfilar solo lo que pensás usar.** Las columnas que descartás también se miden: la decisión de descartarlas tiene que apoyarse en algo.
- **Confiar en documentación previa** sobre claves, tipos o cardinalidades. Se verifica contra las filas.
