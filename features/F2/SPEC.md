# F2 Search for unique files by metadata

## 1 Why is this useful?

When the same bytes exist at several locations (back‑ups, hard‑links, cloud mounts …), **Home‑Index** stores **one canonical document per unique file** and tracks every place it is found.
You can therefore filter or search on file‑wide properties — size, MIME type, modification time, duplicate count — without being distracted by copies.

```
output/
└── metadata/
    ├── by-id/<hash‑of‑file>/document.json        # exactly one per unique file
    └── by-path/<relative‑path> -> ../by-id/<hash‑of‑file>   # symlink
```

Each `document.json` contains at least:

| Field        | Meaning                                                                                          |
| ------------ | ------------------------------------------------------------------------------------------------ |
| `id`         | The hexadecimal file hash (**xxhash64 by default**; future releases may add configuration).      |
| `paths`      | Map <`relative‑path` → `mtime`>.                                                                 |
| `paths_list` | Array of relative paths (handy for Meilisearch filters).                                         |
| `size`       | File size in bytes.                                                                              |
| `mtime`      | Latest modification time among all copies (UNIX epoch **seconds**, float with 4‑dec. precision). |
| `type`       | MIME type detected by libmagic.                                                                  |
| `copies`     | `paths_list.length` – number of identical copies.                                                |

*Additional internal fields such as `version`, `next`, `offline`, or `has_archive_paths` may also appear and can be ignored by consumers.*

All listed fields are **filterable** in the **files** index, e.g.:

```bash
curl -X POST 'http://localhost:7700/indexes/files/search' \
     -H 'Content-Type: application/json' \
     -d '{"q":"","filter":"copies = 1 AND type = \"image/jpeg\""}'
```

---

## 2 How documents are (re)built

1. **Scan step** – Walk every path under the configurable `INDEX_DIRECTORY` (default `/files`), compute the content hash, emit `<relative‑path, hash>`.
2. **Index step** – For each hash:

   * Create or update `by-id/<hash>/document.json`.
   * Ensure a symlink `by-path/<relative‑path>` points to that directory.
3. **Detecting change** – Executed by the scheduled sync job (cron defined in **F1**):

   * **New copy** of existing bytes → `copies` increments; symlink added.
   * **Deleted copy** → path entry removed; `copies` decrements (document remains while ≥ 1 copy exists).
   * **File modified** (hash changes) → old document retains the old hash; new document created.

No restart is needed; **the next scheduled sync** (every minute by default) picks up changes automatically.

---

## 3 Minimal `docker-compose.yml`

```yaml
services:
  home-index:
    image: ghcr.io/nashspence/home-index:latest
    environment:
      - METADATA_DIRECTORY=/home-index/metadata
      # Optional overrides already honoured by the code:
      # - INDEX_DIRECTORY=/files
      # - BY_ID_DIRECTORY=metadata/by-id
      # - BY_PATH_DIRECTORY=metadata/by-path
      # - CRON_EXPRESSION=* * * * *         # scan every minute
    volumes:
      - ./input:/files:ro
      - ./output:/home-index
    depends_on: [meilisearch]

  meilisearch:
    image: getmeili/meilisearch:latest
    environment: [MEILI_NO_ANALYTICS=true]
    volumes: [./output/meili:/meili_data]
    ports: ["7700:7700"]
```

---

## 4 Acceptance criteria (platform‑agnostic)

| #      | Scenario & pre‑conditions                                                                                       | Steps (actions → expected result)                                                                                                                                                                                                 |
| ------ | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1**  | **Initial sync with duplicates present**<br>`<file‑A>` and `<file‑B>` are byte‑identical; `<file‑C>` is unique. | 1 Start stack → Exactly **two** directories appear under `by-id/` (one shared by A & B, one for C).<br>2 `by-path/` contains one symlink per original *relative* path; the two for A & B resolve to the same target. ([test](tests/acceptance/test_s1.py)) |
| **2**  | **Document fields populated**                                                                                   | 1 Open any generated `document.json` → Fields `id`, `paths`, `paths_list`, `mtime`, `size`, `type`, `copies` all exist and have correct values (e.g., duplicate shows `copies > 1`); `mtime` is a float seconds. ([test](tests/acceptance/test_s2.py))                  |
| **3**  | **Search by single criterion**                                                                                  | 1 Query **files** index with `filter: "copies = 1"` (or any single‑field filter) → Response returns only documents whose `copies` equal 1.                                                                                         ([test](tests/acceptance/test_s3.py)) |
| **4**  | **Search by multiple criteria**                                                                                 | 1 Query with `filter: "size >= 1024 AND type = \"application/pdf\""` → Response contains only documents satisfying **all** clauses.                                                                                                ([test](tests/acceptance/test_s4.py)) |
| **5**  | **Add new duplicate while running**                                                                             | 1 Copy a second instance of `<file‑C>` into `/files`. <br>2 Wait ≤ 1 min → Original document’s `copies` increments by 1 and its `paths`/`paths_list` include the new relative path; no new hash directory created.                 ([test](tests/acceptance/test_s5.py)) |
| **6**  | **Delete one duplicate but not all**                                                                            | 1 Remove one of the multiple paths that reference the same content. <br>2 Wait ≤ 1 min → Document remains; `copies` decrements; removed path no longer appears in `paths_list`.                                                    ([test](tests/acceptance/test_s6.py)) |
| **7**  | **Delete last remaining copy**                                                                                  | 1 Remove the final path of a document. <br>2 Wait ≤ 1 min → Corresponding `by-id/<hash>` directory and all symlinks are deleted; document disappears from search results.                                                          ([test](tests/acceptance/test_s7.py)) |
| **8**  | **File content changes (hash changes)**                                                                         | 1 Edit `<file‑B>` so its bytes differ. <br>2 Wait ≤ 1 min → A **new** document (new hash) is created; old document still exists for any other copies of the old bytes; `by-path/<relative‑path‑of‑B>` now points to the new hash.  ([test](tests/acceptance/test_s8.py)) |
| **9**  | **Symlink integrity**                                                                                           | 1 For any path in `by-path/`, resolve the symlink → It always points to a **relative path** inside `by-id/` and never breaks across restarts or host reboots.                                                                      ([test](tests/acceptance/test_s9.py)) |
| **10** | **Search returns latest metadata after change**                                                                 | 1 After Scenario 5, query `filter: "copies > 1"` → Newly incremented document appears without restarting Meilisearch or Home‑Index.                                                                                                ([test](tests/acceptance/test_s10.py)) |

**Test‑harness note** – ensure `CRON_EXPRESSION` is set short enough (e.g. `* * * * *`) so scenarios complete within one minute between syncs.

All ten scenarios **must pass** on Linux, macOS, and Windows (WSL) without altering the specification wording—only concrete file names, paths, sizes and types may change in test fixtures.

---

**End of specification**
