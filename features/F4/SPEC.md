# F4 Modules enrich your project files

## 1 Why use modules?

A **module** is a self‑contained worker (Docker container) that analyses each file and adds extra artefacts—EXIF tags, OCR text, AI captions, thumbnails …—to the Home‑Index metadata store. Each module runs in its own container and talks to the core service through **Redis queues**.

### What’s in it for you?

* **Richer, faster search** – as soon as a module finishes, its data is merged into `document.json` and re‑indexed in Meilisearch.
* **Hands‑off operation** – modules wake only when work is waiting and never block the normal file‑sync loop.
* **Easy upgrades** – drop a new module in `MODULES`; Home‑Index will re‑queue everything from that module onward without manual steps.

### 1.1 Archive‑first queue ordering

When the scanner walks the tree it creates two tiers of jobs:

| Tier  | Condition on the file                                                | In‑tier order |
| ----- | -------------------------------------------------------------------- | ------------- |
| **A** | `has_archive_paths =true` **and** the drive is **currently mounted** | lexical path  |
| **B** | all other files                                                      | lexical path  |

Tier A always drains before Tier B. If a drive in Tier A is unplugged mid‑run, its remaining jobs pause until the drive re‑appears.

### 1.2 Effect of module list / UID changes

At start‑up Home‑Index

1. Loads the configured `MODULES` list (name + uid + order) and compares it with the list persisted in `modules_state.json`.
2. Finds the **first change‑point** and re‑queues every file from that module onward.

All files on affected drives flip their marker to `‑status-pending`; they return to `‑status-ready` only when the new module versions have finished (see **F3**).

### 1.3 Version tolerance

Modules **must remain forward‑compatible**: documents written by older versions stay searchable until the drive is re‑mounted and re‑indexed. A module must **never crash** simply because an archive has not yet been migrated.

### 1.4 Resource share‑group tokens

When two or more containers require the **same scarce resource**—a GPU, a licensed binary, a single network port—each advertises the groups it belongs to through `RESOURCE_SHARES` (see §2.3). Home‑Index hands out **tokens** for every group.
A worker may only enter its `run()` phase when it simultaneously holds **all** tokens declared in its YAML. Tokens:

* rotate round‑robin between group members;
* are held for at most `seconds` before being yielded;
* carry a time‑to‑live so that a crashed worker frees the resource automatically.

---

## 2 Configure the pipeline

### 2.1 Declare modules (order + UID)

```yaml
MODULES: |
  - name: vision-module
    uid: "bb07dfb4-3b2e-4f26-9a37-81ba0f227391"
  - name: text-module
    uid: "a0648b3c-114d-4eb4-a4c7-70e8b5c9d888"
```

* **Order matters** – files flow top → bottom, but archive Tier A still schedules ahead of Tier B.
* Each `uid` is printed by the module’s build template; copy (or script) it into `MODULES`.
* A change in **name / uid / order** is the **re‑queue point** (§1.2).

### 2.2 Environment variables inside every module container

| Variable                              | Required | Meaning                                                                                                |
| ------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------ |
| `MODULE_NAME`<br>`QUEUE_NAME` (alias) | ✔        | Must equal the `name` in `MODULES`.                                                                    |
| `MODULE_UID`                          | ✔        | Must equal the `uid` in `MODULES`. The worker **skips** queue items whose embedded uid differs (§3‑2). |
| `REDIS_HOST`                          | ✔        | Redis connection string.                                                                               |
| `TIMEOUT`                             | ✖        | Seconds after which Home‑Index retries the job *(default 30)*.                                         |
| `WORKER_ID`                           | ✖        | Distinguishes identical containers inside one share‑group rotation.                                    |
| `RESOURCE_SHARES`                     | ✖        | YAML list of share groups – see §2.3.                                                                  |
| `METADATA_DIRECTORY`                  | ✖        | Where to write artefacts (default `/home-index/metadata`).                                             |

### 2.3 Sharing scarce resources (`RESOURCE_SHARES`)

Set `RESOURCE_SHARES` to a YAML sequence; each entry defines one group:

```yaml
RESOURCE_SHARES: |
  - name: gpu
    seconds: 30
  - name: licence
    seconds: 5
```

* **Round‑robin** – only one worker in the same group may run at a time; turns alternate automatically.
* **Time slice** – after `seconds` the token is yielded to the next container.
* **TTL** – if a container crashes or stalls, its token expires and the queue continues.
* Declare **multiple groups** to require combined access: a job starts only when it holds **all** groups (e.g. `gpu` + `licence`).
  Omit `RESOURCE_SHARES` if unrestricted parallelism is safe.

---

## 3 Runner semantics (check → run loop)

1. **Home‑Index** enqueues `<module>:check` items in the archive‑first order (§1.1).
2. The module container **peeks** at the head of its queue:

   * **UID matches** → pull job and call `check`. If `check(file, doc, meta_dir)` returns *True* call `run(...)`.
   * **UID differs** → log a warning, leave the item on the queue, **sleep 10 minutes**.
3. Before entering `run()` the worker must **acquire all share‑group tokens** declared in its `RESOURCE_SHARES`; otherwise it waits.
4. On completion the worker pushes its summary onto the done queue.

   * Home‑Index merges any `document` keys, rebuilds chunks, updates Meilisearch, and—if the file lives on an archive drive—re‑evaluates the drive marker (see **F3**).
5. Re‑building a module with a **new UID** triggers a re‑queue from that module onward; affected drives flip to `‑status-pending` until the new run finishes.

Directory layout per file hash:

```
output/metadata/by-id/<file‑hash>/
├── document.json            # merged document (all modules)
└── <module‑name>/           # one sub‑dir per module
    ├── content.json         # raw text / segment list (optional)
    ├── chunks.json          # auto‑chunked search docs
    ├── log.txt              # stdout / stderr from last run
    └── …                    # other artefacts the module writes
```

**Progress tracking – the `next` field**

`document.json` always contains `"next"` (propagated to Meilisearch):

* Its value is the **name of the next module** still to process this file, e.g. `"text-module"`.
* It becomes `""` once the file has cleared the entire `MODULES` chain.

---

## 4 Writing a module

```python
from features.F4.home_index_module import run_server

def check(file_path, document, metadata_dir):
    """Fast, side‑effect‑free test: should run() execute?"""
    return not (metadata_dir / "chunks.json").is_file()

def run(file_path, document, metadata_dir):
    """Heavy work. Return data for Home‑Index to merge & index."""
    updated_doc = {"detected_labels": ["cat", "tree"]}
    raw_text    = "A cat is climbing a tree."
    return {"document": updated_doc, "content": raw_text}

if __name__ == "__main__":
    run_server(check, run)
```

`run_server` automatically

* polls check/run queues,
* verifies per‑item uid,
* negotiates share‑group tokens,
* enforces `TIMEOUT`,
* captures per‑file `log.txt`, and
* pushes results back to Home‑Index.

### 4.1 Return‑value contract

| Key          | Type                | Effect                                                           |
| ------------ | ------------------- | ---------------------------------------------------------------- |
| `"document"` | `dict`              | Merged into `document.json` then re‑indexed in Meilisearch.      |
| `"content"`  | `str` ∕ `list`      | Saved to `content.json`; Home‑Index auto‑chunks to `chunks.json` |
| *others*     | serialisable values | Ignored by Home‑Index (artefacts may still be stored manually).  |

---

## 5 Acceptance criteria

| #  | Scenario                               | Steps → Expected result                                                                                                                                          |
| -- | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | **Initial enrichment**                 | Start stack → archive drives (if mounted) process first; their markers flip `pending → ready`; all files searchable.                                              ([test](tests/acceptance/test_s1.py)) |
| 2  | **Plug‑in archive drive**              | Mount `<drive‑X>` whose files are outdated → its jobs jump to front of queue; after modules finish the marker becomes `‑status-ready`.                            ([test](tests/acceptance/test_s2.py)) |
| 3  | **Remove drive mid‑run**               | Unmount during processing → remaining jobs pause; marker stays `‑status-pending`; on next mount they resume and marker flips to `‑status-ready`.                  ([test](tests/acceptance/test_s3.py)) |
| 4  | **UID / order change**                 | Change a module UID or reorder list → restart stack → files re‑queued from that module; affected drives flip `pending` and back to `ready` when done.             ([test](tests/acceptance/test_s4.py)) |
| 5  | **Status files ignored**               | Create `Foo-status-ready` inside archive root → modules ignore it; no artefacts created; file never appears in search.                                            ([test](tests/acceptance/test_s5.py)) |
| 6  | **Non‑archive files unaffected**       | While an archive runs, add a regular file → it waits until Tier A empties, then processes normally.                                                               ([test](tests/acceptance/test_s6.py)) |
| 7  | **Legacy docs still searchable**       | Index contains docs from an old module version → search works before and after re‑queue; no crashes allowed.                                                      ([test](tests/acceptance/test_s7.py)) |
| 8  | **Run‑timeout**                        | Module exceeds `TIMEOUT` → job re‑queued; after fix, completes successfully.                                                                                      ([test](tests/acceptance/test_s8.py)) |
| 9  | **Check‑timeout**                      | `check` hangs → job re‑queued; after fix, completes successfully.                                                                                                 ([test](tests/acceptance/test_s9.py)) |
| 10 | **Restart, no change**                 | Restart with unchanged `MODULES` → no jobs re‑queued; markers unchanged.                                                                                          ([test](tests/acceptance/test_s10.py)) |
| 11 | **Queue‑item uid mismatch**            | Leave stale items with old uid in queue → module logs warning, skips them, retries after 10 min; once Home‑Index re‑queues with correct uid, processing resumes.  ([test](tests/acceptance/test_s11.py)) |
| 12 | **Wrong `MODULE_UID` env var**         | Start container whose `MODULE_UID` does not appear in `MODULES` → container logs fatal mis‑configuration and exits.                                               ([test](tests/acceptance/test_s12.py)) |
| 13 | **Parallel modules & crash isolation** | Two modules run; if one crashes the other still finishes; crash frees any share tokens it held.                                                                   ([test](tests/acceptance/test_s13.py)) |
| 14 | **Share‑group rotation**               | Two containers share `{name: gpu}` → turns alternate; module requiring `gpu` + `licence` runs only when holding both tokens; no starvation.                       ([test](tests/acceptance/test_s14.py)) |
| 15 | **Meilisearch update propagation**     | Module returns new `document` / `content` → Home‑Index merges JSON, rebuilds chunks, Meilisearch reflects updates immediately.                                    ([test](tests/acceptance/test_s15.py)) |

All fifteen scenarios **must pass without editing this specification**—only module names, UIDs, drives, paths and share‑group names may vary.

---

**End of specification**
