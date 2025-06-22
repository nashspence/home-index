# F1 "I want my home server to be available when I need it."

## Value

This feature ensures that home-index not only adheres to a predictable and configurable sync schedule, but also guarantees meaningful progress and data availability when it matters most—aligning directly with your desire for your server to "be available when you need it." By interpreting the cron expression at startup, the daemon spaces sync events precisely to avoid overuse of system resources (P₁), ensures that a critical mass of indexing activity happens soon after startup (P₂), and confirms that tangible results (indexed file metadata) are eventually produced even if the server is stopped early (P₃). Altogether, this contract offers strong assurances of timely responsiveness, visible output, and efficient operation, so your server delivers reliable, ready-to-use file metadata when you interact with it—without wasting energy or leaving you uncertain about whether it's doing its job.

## Specification

### Vocabulary

| Kind       | Syntax on the trace | Payload / meaning                                                                                                                                              |
| ---------- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **input**  | `SET_CRON(c)`       | user (or CI release script) sets the container-env var `CRON_EXPRESSION` to the cron string `c` **once, before start-up**. `c` must follow POSIX cron grammar. |
| **input**  | `START`             | user launches the stack (e.g. `docker compose up -d`).                                                                                                         |
| **output** | `LOG_SYNC(t)`       | the container writes a log line that *begins* with the **exact timestamp** `t ∈ ℝ₊` and contains the literal text `"start file sync"`.                         |
| **output** | `FILES_READY`       | the directory `metadata/by-id` has become non-empty (first time only—later duplicates are ignored).                                                            |

The trace is a finite or infinite time-ordered sequence
`e₀ e₁ e₂ …`, each `eᵢ` chosen from the four event shapes above.

---

### Helper — deterministic interval function

```
interval : CronString → ℝ₊
interval("* * * * *")   = 60
interval("*/2 * * * *") = 120
…  (standard crontab semantics for any valid c)
```

---

### Contract = P₁ ∧ P₂ ∧ P₃   (all formulas use continuous-time MTL)

Let **`I ≜ interval(c₀)`**, where `c₀` is the payload of the unique `SET_CRON`
event in the trace.

| Label                     | MTL formula                                                            | Natural-language reading                                                                                                                                                   |
| ------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P₁ spacing**            | `G( LOG_SYNC(t)  →  G_(0, I) ¬LOG_SYNC )`                              | *After every log-sync, no second log-sync appears for **strictly** `I` seconds.*                                                                                           |
| **P₂ cadence & quantity** | `G( (¬SYNC_SEEN ∧ START)  →  F_[0, 3I+120]  (SYNC₁ ∧ SYNC₂ ∧ SYNC₃) )` | *From the instant the stack is started, at least three log-syncs arrive within `3 · I + 120 s`. (The helper predicates `SYNC₁ … SYNC₃` count distinct `LOG_SYNC` events.)* |
| **P₃ artefacts**          | `G( STOP  →  F FILES_READY )`                                          | *Whenever the user stops the stack, the metadata directory eventually contains at least one file.*                                                                         |
