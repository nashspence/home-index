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

```gherkin
@f2
Feature: Search for unique files by metadata

  Rule: Index creation
    @s1
    # [test](tests/acceptance/test_s1.py)
    Scenario: Initial sync with duplicates present
      Given <file-A> and <file-B> are identical and <file-C> is unique
      When the stack boots
      Then the logs contain, in order:
        | container  | line_regex                                |
        | home_index | ^\[INFO\] start file sync$                |
        | home_index | ^\[INFO\] commit changes to meilisearch$ |
        | home_index | ^\[INFO\] completed file sync$            |
      And the logs contain, in order:
        | container  | line_regex                                |
        | home_index | ^\[INFO\] start file sync$                |
        | home_index | ^\[INFO\] commit changes to meilisearch$ |
        | home_index | ^\[INFO\] completed file sync$            |
      And exactly two directories exist under $METADATA_DIRECTORY/by-id/
      And $METADATA_DIRECTORY/by-path/a.txt and b.txt resolve to the same target

    @s2
    # [test](tests/acceptance/test_s2.py)
    Scenario: Document fields populated
      Given the stack has booted
      When the logs contain, in order:
          | container  | line_regex                                |
          | home_index | ^\[INFO\] start file sync$                |
          | home_index | ^\[INFO\] commit changes to meilisearch$ |
          | home_index | ^\[INFO\] completed file sync$            |
      Then any generated document.json is read
        And it contains fields id, paths, paths_list, size, mtime, type and copies
        And duplicates show copies greater than 1

  Rule: Querying documents
    @s3
    # [test](tests/acceptance/test_s3.py)
    Scenario: Search by single criterion
      Given the stack has booted
      When the logs contain, in order:
          | container  | line_regex                                |
          | home_index | ^\[INFO\] start file sync$                |
          | home_index | ^\[INFO\] commit changes to meilisearch$ |
          | home_index | ^\[INFO\] completed file sync$            |
      Then the files index is queried with filter "copies = 1"
        And only documents with copies = 1 are returned

    @s4
    # [test](tests/acceptance/test_s4.py)
    Scenario: Search by multiple criteria
      Given the stack has booted
      When the logs contain, in order:
          | container  | line_regex                                |
          | home_index | ^\[INFO\] start file sync$                |
          | home_index | ^\[INFO\] commit changes to meilisearch$ |
          | home_index | ^\[INFO\] completed file sync$            |
      Then the files index is queried with filter "size >= 1024 AND type = \"application/pdf\""
        And only documents satisfying all clauses are returned

  Rule: Updating metadata
    @s5
    # [test](tests/acceptance/test_s5.py)
    Scenario: Add new duplicate while running
      Given the stack has booted
      When the logs contain, in order:
          | container  | line_regex                                |
          | home_index | ^\[INFO\] start file sync$                |
          | home_index | ^\[INFO\] commit changes to meilisearch$ |
          | home_index | ^\[INFO\] completed file sync$            |
      Then a second copy of <file-C> is added
        And the logs contain, in order:
        | container  | line_regex                                |
        | home_index | ^\[INFO\] start file sync$                |
        | home_index | ^\[INFO\] commit changes to meilisearch$ |
        | home_index | ^\[INFO\] completed file sync$            |
      And the existing document's copies increment
        And no new hash directory is created

    @s6
    # [test](tests/acceptance/test_s6.py)
    Scenario: Delete one duplicate but not all
      Given the stack has booted with duplicates present
      When the logs contain, in order:
          | container  | line_regex                                |
          | home_index | ^\[INFO\] start file sync$                |
          | home_index | ^\[INFO\] commit changes to meilisearch$ |
          | home_index | ^\[INFO\] completed file sync$            |
      Then one path is removed
        And the logs contain, in order:
        | container  | line_regex                                |
        | home_index | ^\[INFO\] start file sync$                |
        | home_index | ^\[INFO\] commit changes to meilisearch$ |
        | home_index | ^\[INFO\] completed file sync$            |
      And the document remains with copies decremented
        And the removed path no longer exists

    @s7
    # [test](tests/acceptance/test_s7.py)
    Scenario: Delete last remaining copy
      Given the stack has booted with duplicates present
      When the logs contain, in order:
          | container  | line_regex                                |
          | home_index | ^\[INFO\] start file sync$                |
          | home_index | ^\[INFO\] commit changes to meilisearch$ |
          | home_index | ^\[INFO\] completed file sync$            |
      Then the final path is removed
        And the logs contain, in order:
        | container  | line_regex                                |
        | home_index | ^\[INFO\] start file sync$                |
        | home_index | ^\[INFO\] commit changes to meilisearch$ |
        | home_index | ^\[INFO\] completed file sync$            |
      And the hash directory and symlinks disappear
        And the document vanishes from search results

    @s8
    # [test](tests/acceptance/test_s8.py)
    Scenario: File content changes
      Given the stack has booted with duplicates present
      When the logs contain, in order:
          | container  | line_regex                                |
          | home_index | ^\[INFO\] start file sync$                |
          | home_index | ^\[INFO\] commit changes to meilisearch$ |
          | home_index | ^\[INFO\] completed file sync$            |
      Then a duplicate file's bytes are modified
        And the logs contain, in order:
        | container  | line_regex                                |
        | home_index | ^\[INFO\] start file sync$                |
        | home_index | ^\[INFO\] commit changes to meilisearch$ |
        | home_index | ^\[INFO\] completed file sync$            |
      And a new document is created for the new hash
        And the old document remains for remaining copies

  Rule: Symlinks and fresh results
    @s9
    # [test](tests/acceptance/test_s9.py)
    Scenario: Symlink integrity
      Given the stack has booted
      When the logs contain, in order:
          | container  | line_regex                                |
          | home_index | ^\[INFO\] start file sync$                |
          | home_index | ^\[INFO\] commit changes to meilisearch$ |
          | home_index | ^\[INFO\] completed file sync$            |
      Then the stack was stopped
        And the stack has booted again
        And any symlink in $METADATA_DIRECTORY/by-path/ is resolved
        And it always points to a relative path inside $METADATA_DIRECTORY/by-id/
        And the logs contain, in order:
          | container  | line_regex                                |
          | home_index | ^\[INFO\] start file sync$                |
          | home_index | ^\[INFO\] commit changes to meilisearch$ |
          | home_index | ^\[INFO\] completed file sync$            |

    @s10
    # [test](tests/acceptance/test_s10.py)
    Scenario: Search returns latest metadata after change
      Given an extra copy of a file was added
      When the logs contain, in order:
          | container  | line_regex                                |
          | home_index | ^\[INFO\] start file sync$                |
          | home_index | ^\[INFO\] commit changes to meilisearch$ |
          | home_index | ^\[INFO\] completed file sync$            |
      Then the files index is queried with filter "copies > 1"
        And the newly updated document appears in results
```

All ten scenarios **must pass** on Linux, macOS, and Windows (WSL) without altering the specification wording—only concrete file names, paths, sizes and types may change in test fixtures.

---

**End of specification**
