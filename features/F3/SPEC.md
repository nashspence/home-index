# F3 Offline media to remains searchable

## 1 Why special support for offline media?

Removable media (USB disks, SD cards, external SSDs, network shares, …) are not always attached.
Home‑Index keeps their file metadata so you can still

* search for a file even when its drive is unplugged,
* know **which** drive you must plug in to regain access,
* resume syncing the moment the drive re‑appears, and
* see **at a glance** (via a small marker file) whether the drive has been fully processed.

---

## 2 How it works

### 2.1 Configure an “archive root”

```yaml
environment:
  ARCHIVE_DIRECTORY: /files/archive # default shown
```

*Every sub‑directory directly under this path represents one removable medium.*
For each of those drive directories `<drive‑X>` Home‑Index maintains **one adjacent marker file**:

```
<drive‑X>-status-ready      # all modules finished for this drive
<drive‑X>-status-pending    # one or more modules still need to run (see F4)
```

The file contains a single ISO‑8601 timestamp of the last successful *sync* that touched the drive.
Marker files live **next to** the drive directory (i.e. inside `ARCHIVE_DIRECTORY`, not inside the drive itself) and are **never indexed**.

### 2.2 Behaviour during every sync

1. **Classification**

   * If **all** paths of a document live in the archive root → the document is classed as *archived*.
2. **Symlink map**

   * Each archived file gets a symlink under
     `output/metadata/by-path/archive/<drive‑X>/<relative-path>` → `output/metadata/by-id/<file-hash>`.
3. **State flags on every document**

| Field               | Meaning                                                                         |
| ------------------- | ------------------------------------------------------------------------------- |
| `has_archive_paths` | `true` iff the document has ≥ 1 path beneath `ARCHIVE_DIRECTORY`.               |
| `offline`           | `true` iff **all** archive paths are currently unavailable (drive not mounted). |

4. **Archive‑status marker maintenance**
   For every `<drive‑X>` seen during the scan:

   * Evaluate whether any file on the drive still requires a module run (see F4).

     * **Yes** → write/refresh `<drive‑X>-status-pending` with the current UTC time.
     * **No**  → ensure `<drive‑X>-status-ready` exists with the current UTC time.
   * Whichever status file is written, the other (if present) is removed.
   * Files whose basename matches `*-status-(pending|ready)` are skipped by all indexers and modules.

5. **Version tolerance**
   Home‑Index and every module **must remain forward‑compatible**: documents produced by *older* module versions stay searchable until the drive is remounted and re‑indexed. No immediate migration pass is required.

### 2.3 Drive status marker files (summary)

| Location               | Example                      |
| ---------------------- | ---------------------------- |
| Directory              | `/files/archive`             |
| Ready marker           | `MyUKSBDisk-status-ready`    |
| Pending marker         | `MyUKSBDisk-status-pending`  |
| Contents               | `2025-07-18T16:23:01Z` (UTC) |
| Update cadence         | Every sync                   |
| Indexed by Home‑Index? | **Never**                    |

---

## 3 Minimal `docker-compose.yml`

*(unchanged; shown for completeness)*

```yaml
services:
  home-index:
    image: ghcr.io/nashspence/home-index:latest
    environment:
      ARCHIVE_DIRECTORY: /files/archive
      METADATA_DIRECTORY: /home-index/metadata
      REDIS_HOST: http://redis:6379
    volumes:
      - ./input:/files:ro
      - ./output:/home-index
    depends_on: [meilisearch]

  meilisearch:
    image: getmeili/meilisearch:latest
    environment: [MEILI_NO_ANALYTICS=true]
    volumes: [./output/meili:/meili_data]
```

---

## 4 Acceptance criteria (platform‑agnostic)

Any operating system (Linux, macOS, Windows + WSL) may be used.
Placeholders:

* `<drive‑X>` — a directory directly under `ARCHIVE_DIRECTORY` (e.g. `MyUSB`).
* `<file‑A>` — a regular file somewhere inside the drive root.

| #  | Scenario & pre‑conditions                                     | Steps (user actions → expected result)                                                                                                                                                                             |
| -- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1  | **Drive online**<br>`<file‑A>` exists on mounted `<drive‑X>`. | 1 Start sync → Symlink `by-path/archive/<drive‑X>/…/<file‑A>` points to `by-id/<hash-A>`.<br>2 Flags `has_archive_paths =true`, `offline =false`.<br>3 Marker file `<drive‑X>-status-ready` contains current time. ([test](tests/acceptance/test_s1.py)) |
| 2  | **Drive unplugged**                                           | 1 Unmount/remove `<drive‑X>`.<br>2 Sync → Symlink & `by-id` remain; flags `offline =true`; marker unchanged. ([test](tests/acceptance/test_s2.py))                                                                                                       |
| 3  | **Drive re‑attached *with* the file**                         | 1 Mount `<drive‑X>` containing `<file‑A>`.<br>2 Sync → Flags `offline =false`; marker refreshed. ([test](tests/acceptance/test_s3.py))                                                                                                                   |
| 4  | **Drive re‑attached *without* the file**                      | 1 Mount `<drive‑X>` but delete `<file‑A>`.<br>2 Sync → Symlink & `by-id/<hash-A>` removed; document disappears from search; marker becomes `-status-ready`. ([test](tests/acceptance/test_s4.py))                                                        |
| 5  | **File copied to archive while drive is online**              | 1 Add `<file‑B>` to `<drive‑X>`.<br>2 Sync → New `by-id/<hash‑B>` and symlink; drive marker flips to `-status-pending` until all modules finish. ([test](tests/acceptance/test_s5.py))                                                                   |
| 6  | **File exists on both archive and regular path**              | 1 Place identical bytes of `<file‑C>` in a non‑archive path and on `<drive‑X>`.<br>2 Sync → One `by-id` folder; flags `offline =false` (online copy). `-status-ready` persists. ([test](tests/acceptance/test_s6.py))                                    |
| 7  | **Online copy deleted – archive offline**                     | 1 Delete non‑archive copy of `<file‑C>`; unmount `<drive‑X>`.<br>2 Sync → Flags `offline =true`; document still searchable; marker unchanged. ([test](tests/acceptance/test_s7.py))                                                                      |
| 8  | **Archive root renamed or moved**                             | 1 Unmount `<drive‑X>`; remount under new name `<drive‑Y>`.<br>2 Sync → Old symlinks removed; new symlinks under `<drive‑Y>`; marker file renamed accordingly and refreshed. ([test](tests/acceptance/test_s8.py))                                        |
| 9  | **Multiple drives tracked independently**                     | 1 Mount `<drive‑X>` (online), leave `<drive‑Z>` unplugged.<br>2 Sync → Each drive keeps its own marker and flags; actions on one never alter the other. ([test](tests/acceptance/test_s9.py))                                                            |
| 10 | **Change of `ARCHIVE_DIRECTORY` path**                        | 1 Stop stack after a successful run.<br>2 Move drives + marker files; update env var; restart.<br>3 Sync → Symlinks regenerated, markers honoured, flags accurate. ([test](tests/acceptance/test_s10.py))                                                 |
| 11 | **Status files themselves are ignored**                       | 1 Create a dummy text file `Foo-status-ready` inside `ARCHIVE_DIRECTORY`.<br>2 Sync → No symlink or search document appears for that file. ([test](tests/acceptance/test_s11.py))                                                                         |
| 12 | **Module update triggers re‑queue**                           | 1 Re‑build a module with a new UID (per F4).<br>2 Restart stack → Home‑Index re‑queues files; drive marker flips to `-status-pending` and back to `-status-ready` once all modules finish.                         |

All twelve scenarios must succeed *without editing this specification*—only drive names, file names, and mount points vary per project.

---

**End of specification**
