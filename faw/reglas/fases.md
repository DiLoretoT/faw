# Las fases, operativamente

Qué hace el agente en cada una, qué produce y qué tiene que ser cierto para cerrarla.

---

## 1. CLASIFICACIÓN

**Objetivo:** entender el pedido, asignar tier, no arrancar a construir lo que no se pidió.

Se hace:
1. Reformular el pedido en una frase. Si la reformulación no es obvia, preguntar antes de seguir.
2. Mirar el estado real: rama actual, working tree, últimas transiciones en `.faw/estado.jsonl`, artefactos que el pedido toca.
3. Asignar tier y **justificarlo en una línea**.
4. Definir alcance explícito: qué entra y **qué no**.
5. Crear rama `<tipo>/<slug>` si el tier la necesita.

Se produce: la clasificación, en el chat. Sin documento, salvo el ticket cuando el proyecto usa el registro interno.

**De dónde sale el identificador del trabajo.** Lo declara `tickets.sistema` en `faw.json`. Con un gestor externo, el identificador sale de ahí y se pasa con `--ticket`; con el registro interno, lo genera FAW y crea el archivo del ticket en `docs/faw/tickets/`. Que el gestor externo tenga o no un servidor MCP conectado cambia quién lo opera, no el método: con MCP el agente consulta y actualiza; sin MCP, el usuario opera su herramienta e informa el identificador.

**Cuando el pedido no alcanza para clasificar bien.** Si falta entender el origen, falta una definición de negocio, o hay una decisión de plataforma que depende de datos sin medir, no se avanza a fuerza de supuestos. Se le ofrece al usuario abrir una **consulta previa**: un trabajo de tier `CONSULTA` acotado a responder exactamente esas dudas, que produce un documento en `docs/faw/consultas/`. Ese documento se pasa después al abrir el trabajo real:

```bash
python <faw>/scripts/estado.py iniciar --tier ARTEFACTO --titulo "..." \
    --contexto docs/faw/consultas/<id>.md
```

Al abrir el trabajo real **no se vuelve a preguntar lo que el usuario ya contestó**: se le reconfirma en una línea lo que quedó decidido y se le piden únicamente los datos nuevos.

**Cierre — punto de control 1 de 3:** el usuario confirma tier y alcance. Acá se decide cuánto proceso va a costar el resto.

**Si el tier es `REPORTE`, CLASIFICACIÓN incluye el brief.** No se entra a construir un reporte sin haber acordado **con el usuario** para qué existe: objetivo, audiencia, las preguntas que tiene que responder, qué no entra, origen de datos y quién valida los números. Se llena en `docs/faw/<ticket>/brief.md` desde `faw/contratos/PLANTILLA.brief.md`, y lo verifica `scripts/verificar_brief.py`. Deducir el alcance leyendo el modelo semántico no es clasificar: es construir el brief solo, sin la conversación que lo valida. La skill oficial `powerbi-report-planning` cubre la mecánica de esta conversación; leerla antes.

---

## 2. PERFILADO

**Objetivo:** que el diseño se apoye en números y no en supuestos.

Se hace, según lo que el pedido toque:

**Origen (tabla nueva o entidad no perfilada antes)**
- Filas totales.
- Clave natural candidata: `count(*)` contra `count(distinct)`. Si no coinciden, no es la clave — se buscan discriminadores.
- Por cada columna que Gold va a consumir: nulos, distinct, mínimo y máximo.
- Centinelas del origen y su porcentaje real de aparición.
- Tipos reales, no los de la ficha.

**Gold existente (tiers `MODELO` y `REPORTE`)**
- Filas y columnas de cada tabla que el modelo va a consumir.
- Totales de negocio que el reporte debería reproducir.
- Distribución de las dimensiones sobre las que se va a segmentar.

**Síntoma (tier `INCIDENTE`)**
- Qué se esperaba, qué se obtuvo, desde cuándo.
- Historial del artefacto: última escritura, último cambio de esquema.

Se produce: `docs/faw/<ticket>/perfilado.md`, con **cada número acompañado de la consulta que lo produjo**.

**Cierre — compuerta `perfil`, sin parar.** Existe el recibo y contiene consultas, no solo resultados. El agente muestra el recibo y sigue directo a DISEÑO — no es punto de control, es tránsito automático.

> Perfilar es solo lectura. Si hace falta escribir algo para perfilar, aplica el principio 3: autorización explícita.

---

## 3. DISEÑO

**Objetivo:** decidir antes de construir, y dejarlo escrito de forma que una máquina pueda verificarlo después.

Se hace:
1. **Grano.** Una frase: "una fila por ___". Si no se puede escribir así, el grano no está decidido.
2. **Clave natural**, la que se verificó en PERFILADO.
3. **Contrato de datos** en `<raíz de artefactos>/contratos/<esquema>.<tabla>.yml`: columnas, tipos, nulabilidad, FKs, reglas de calidad. Ver abajo qué es la raíz de artefactos.
4. **Dónde vive cada transformación.** El criterio: *si al borrar el consumidor de hoy la transformación deja de tener sentido, no va en la capa de abajo.*
5. **Las decisiones de plataforma.** Modo de almacenamiento del modelo semántico, dónde se resuelve cada cálculo, estrategia de carga, convención de nombres. Se plantean y se justifican **siempre**, incluso cuando el usuario no las mencionó y aunque no conozca el tema: la consecuencia de equivocarlas la paga igual, y un valor por defecto que nadie eligió es una decisión que tomó la herramienta. Cada afirmación determinante sobre la plataforma se respalda con documentación oficial leída y fechada. Detalle en la skill `faw-disenar`.
6. **Riesgos.** Qué puede salir mal y cómo se va a detectar. No es ceremonia: cada riesgo se traduce en una aserción o en una métrica de diagnóstico del artefacto.
7. **Impacto.** Qué se rompe si esto cambia: artefactos aguas abajo, modelos semánticos, reportes.

Se produce: el contrato y `<raíz de artefactos>/faw/<ticket>/diseno.md`.

### La raíz de artefactos la decide el usuario

Los contratos, perfilados y diseños contienen razonamiento extenso, alternativas descartadas,
hallazgos abiertos y preguntas de negocio. Por defecto viven en el repo de trabajo (`contratos/`
y `docs/faw/<ticket>/`), y la compuerta `superficie` no revisa esas rutas: son artefactos del
propio método.

Eso solo es correcto si quien lee el repo puede leer ese razonamiento. Cuando no — el repo vive
en la organización de un cliente, o lo lee un tercero que no debe ver trabajo interno — la raíz
se declara fuera del repo en `.faw/config.json` (que no se versiona):

```json
{
  "artefactos_en": "C:/ruta/a/la/documentacion/interna/FAW",
  "personas_cliente": ["Apellido1", "Apellido2"],
  "literales_internos": ["repo-interno", "OtroCliente"]
}
```

FAW no deduce de quién es el repo: trata a todos igual — superficie que lee un tercero, ver
[`cliente.md`](cliente.md) — y el usuario declara lo que no debe filtrarse. `personas_cliente` y
`literales_internos` alimentan la compuerta `superficie`: frena el commit o el PR que nombre a
una persona del cliente o un literal declarado interno. Las dos listas están vacías por defecto.

Dejar los artefactos en el repo sin pensarlo publica trabajo interno — contratos, perfilados,
diseños — donde el lector del repo lo ve. De ahí que la ruta se declare explícita en
`.faw/config.json` cuando ese lector no debe verlo.

**Cierre — punto de control 2 de 3:** el contrato existe, es sintácticamente válido, declara grano/clave/columnas, **y el usuario confirma el diseño antes de construir**. No solo en el primer artefacto de un dominio nuevo — siempre, en `ARTEFACTO` y `MODELO`. Es donde una decisión equivocada cuesta más barato.

---

## 4. CONSTRUCCIÓN

**Objetivo:** implementar y demostrar que corre contra datos reales.

Se hace:
0. Si el tipo de artefacto tiene skill oficial de Microsoft, leerla antes de escribir — mapa en [`skills-microsoft.md`](skills-microsoft.md). La mecánica de plataforma la mantiene el fabricante, no nosotros.
1. Implementar el artefacto.
2. **Las validaciones van adentro del artefacto**, no en un script aparte: aserción de clave natural, guard de esquema, métricas de diagnóstico. Tienen que correr en cada ejecución futura, no solo hoy.
3. Correr contra DEV — con autorización explícita si escribe.
4. Reportar filas **y** columnas, y el resultado de las aserciones.

Se produce: el código, y la tabla o artefacto escrito en DEV.

**Cierre — compuertas `aserciones` y `autorizacion`, sin parar como proceso.** Corrieron y pasaron, y hubo OK explícito para cada escritura — eso último se pide siempre, en el momento de escribir, no es el punto de control de fase. Satisfechas las dos, el agente pasa a VALIDACIÓN.

> Si el artefacto cambia el esquema de una tabla existente, la migración es una decisión aparte que se declara y se autoriza por separado. No es parte de "correr el notebook".

---

## 5. VALIDACIÓN

**Objetivo:** que alguien que no construyó busque el error en vez de confirmar el acierto.

La ejecuta el agente [`faw-validador`](../../agents/faw-validador.md), con el contrato y el recibo de perfilado como entrada, **sin el razonamiento de la construcción**.

Verifica:
1. **Esquema contra contrato** — `scripts/verificar_contrato.py`. Columna por columna.
2. **Números contra el perfilado** — ¿el conteo del artefacto es coherente con lo medido en el origen? Si difiere, ¿está explicado por un filtro declarado en el diseño?
3. **Reglas de calidad del contrato** — nulos, unicidad, dominios.
4. **Modelo semántico**, si aplica — `scripts/verificar_modelo.py`: relaciones, storage mode, `summarizeBy`, `sortByColumn`.
5. **Hallazgos abiertos** con su impacto.

Se produce: `docs/faw/<ticket>/validacion.md` con veredicto **PASA** o **FALLA**.

**Cierre — punto de control 3 de 3:** compuertas `esquema` y, si aplica, `modelo`, **y el usuario ve el veredicto y confirma antes de publicar.**

> Si falla, vuelve a CONSTRUCCIÓN. **No se parchea acá.** El parche lo escribiría el validador y ya no queda nadie mirando desde afuera.

---

## 6. PUBLICACIÓN

**Objetivo:** que lo construido llegue a destino sin llevarse nada por delante.

Se hace:
1. **Verificar el diff completo** — `scripts/verificar_diff.py`. Falla si toca metadata protegida sin declararlo.
2. Commit y push en la rama.
3. PR, siguiendo [`cliente.md`](cliente.md).
4. Merge.
5. **Sincronizar el workspace** y verificar el estado post-deploy: ¿los artefactos conservan su lakehouse por defecto? ¿quedó un diff fantasma? Si quedó y es solo formato, se comitea y se cierra el ciclo.
6. Actualizar el tracker del proyecto con el punto exacto de retomada.

**Cierre — compuertas `git-limpio` y `metadata`.**

> De PUBLICACIÓN no se sale abandonando. Acá no queda nada por decidir, solo pasos por terminar: una salida es un cierre y debe sus compuertas.

---

## Salirse

Desde cualquier fase salvo PUBLICACIÓN, se puede **abandonar** o **pausar**. Hay que decir cuál de las dos.

- **Pausar** registra la fase exacta y el punto de retomada. Reanudar reentra en esa fase.
- **Abandonar** registra por qué. El razonamiento queda en la rama aunque el trabajo no siga.

Bajarse está permitido. Hacerlo en silencio no.
