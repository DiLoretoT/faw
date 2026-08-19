---
name: faw-validate
description: The FAW validation phase. Launches the faw-validator agent so that an agent which did NOT build the artifact checks it against its contract and against what was measured.
---

# Validate

Phase 5 of FAW. **Run by an agent other than the one that built it.**

## Why this is delegated instead of done by you

If you built this, you already decided it is right. Validating it yourself, you
will look for confirmation rather than refutation. Not out of carelessness, but
because of how reviewing your own work goes.

A correct row count proves nothing on its own: a dimension can match the expected
number of rows exactly and still have less than half of its columns. The count was
right, and a review that looks only at the count would have passed it.

That is why this phase is delegated, always, even when it feels like a formality.

## How

Launch the `faw-validator` agent with the contract, the profiling receipt and the
design. **Do not pass it your build reasoning.** If the artifact needs to be
explained in order to be checked, it is badly documented.

```
Agent(subagent_type="faw-validator", prompt="
Validate <artifact> in <environment>.
Contract:  contracts/<schema>.<table>.yml
Profiling: docs/faw/<ticket>/profiling.md
Design:    docs/faw/<ticket>/design.md
Write the verdict to docs/faw/<ticket>/validation.md
")
```

## What it has to return

A verdict of **PASS** or **FAIL**, with:

1. Schema against contract, column by column (`verify_contract.py`).
2. The artifact numbers against the profiling numbers, with differences explained
   by declared filters.
3. The contract quality rules, actually run.
4. The semantic model checked through its definition, where it applies
   (`verify_model.py`).
5. Open findings with their impact.
6. What fell outside its reach, typically business correctness, and who should
   confirm it.

A "passes, but" is a failure that was written politely. Treat it as a failure.

## If it fails

Back to build:

```bash
python <faw>/scripts/state.py move --to BUILD
```

**Do not patch during validation.** The patch would be written by the validator,
and then nobody is left looking from the outside.

## If it passes

```bash
python <faw>/scripts/state.py move --to PUBLICATION \
    --gate schema="ok: 20 columns, matching the contract"
```

For the `MODEL` tier, also `--gate model="ok: ..."` and `--gate
reconciliation="..."`.
