---
name: profile
description: The FAW profiling phase. Measures the source against real data and produces the receipt with the queries behind every number. Use before designing any data artifact.
---

# Profile

Phase 2 of FAW. **No design until there are numbers.**

In software, requirements come from people. In data work, half of them are in the
source and are only discovered by measuring. Every question answered by assumption
produces an artifact that runs and returns the wrong thing.

## The rule that governs this phase

**Every number goes with the query that produced it.** A number without a query
does not enter the receipt.

Profiling is read-only. If something has to be written, ask for explicit
authorization first.

## What to measure

### A new source

```python
# Rows
df.count()

# Candidate natural key. This is what decides whether it is a key
total = df.count()
unique = df.select(*KEY).distinct().count()
print(f"rows={total}  unique={unique}  duplicates={total - unique}")

# For every column the curated layer will consume
df.select([
    F.count(F.when(F.col(c).isNull(), c)).alias(f"{c}_nulls") for c in COLS
]).show()

# Sentinel values in the source, with their real frequency
for c in DATE_COLS:
    df.select(F.round(100 * F.avg((F.col(c) == SENTINEL_LIT).cast("int")), 2)).show()

# Real types, not the ones in the specification
df.printSchema()
```

**The natural key is proven, not copied from a specification.** What documents a
source and what the source is diverge over time. A specification can name a column
the table no longer has, or never had. The key is confirmed by querying the table.

### An existing curated layer (`MODEL` and `REPORT` tiers)

- Rows and columns of every table the model will consume.
- The business totals the report is supposed to reproduce.
- Distribution of the dimensions that will be used for slicing.

### A symptom (`INCIDENT` tier)

What was expected, what was obtained, since when. History of the artifact. Last
write, last schema change.

Urgency does not exempt anyone from measuring. A diagnosis is measured, not
assumed.

## What to produce

`docs/faw/<ticket>/profiling.md`:

```markdown
# Profiling: <entity>
Measured on <date> against <environment>.

## Volume
| Metric | Value | Query |
|---|---:|---|

## Natural key
Candidate: `[...]` - rows N, unique N, duplicates 0.
<query>

## Columns
| Column | Type | Nulls | Distinct | Notes |
|---|---|---:|---:|---|

## Findings
1. ...

## Questions left open
- ... (for the business, with who should answer them)
```

## Closing

```bash
python <faw>/scripts/state.py move --to DESIGN \
    --gate profile=docs/faw/<ticket>/profiling.md
```

## Traps

- **Reporting a number without having measured it.** If you did not measure it,
  write "not measured".
- **Profiling only what you plan to use.** The columns you discard get measured
  too. The decision to discard them has to rest on something.
- **Trusting prior documentation** about keys, types or cardinalities. It gets
  verified against the rows.
