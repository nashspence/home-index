# F5 Search file chunks by concept

## 1 Why concept search?

Exact keywords can miss the passage you need.
F5 lets you issue a *semantic* (vector / hybrid) query that returns the most relevant **chunks** of text even when the words differ.

```
index      : file_chunks
embedder   : intfloat/e5-small‑v2   # default model at start‑up
```

---

## 2 How it works

### 2.1 Generate text once per file

1. Any module you supply outputs **raw text** for every file.
   Home‑Index writes, per file:

```
output/metadata/by-id/<file‑hash>/<text‑module>/
├── content.json   # full text or list of segments (written by your module)
└── chunks.json    # auto‑generated (see § 2.3)
```

### 2.2 Chunk & embed automatically

Environment variables drive the behaviour of **home-index** itself:

| Variable           | Default (code)         | Purpose                                                        |
| ------------------ | ---------------------- | -------------------------------------------------------------- |
| `TOKENS_PER_CHUNK` | **510**                | Target chunk length (tokens) before overlap is added.          |
| `CHUNK_OVERLAP`    | **50**                 | Tokens to repeat at the edges of adjacent chunks (0 – *N*).    |
| `EMBED_MODEL_NAME` | `intfloat/e5-small-v2` | Any model from `sentence‑transformers`; changing it re‑embeds. |

On launch, Home‑Index compares the current values with
`/home-index/chunk_settings.json`.
If **any** of the three differ it triggers a **clean rebuild** of every
`chunks.json` while leaving the corresponding `content.json` untouched.

### 2.3 Chunk document schema

Each item in *any* `chunks.json` **MUST** contain at least these fields:

| Key           | Type   | Meaning                                            |
| ------------- | ------ | -------------------------------------------------- |
| `id`          | string | Stable, unique chunk identifier.                   |
| `file_id`     | string | xxhash of the source file.                        |
| `module`      | string | Name of the module that supplied the text.         |
| `text`        | string | The chunk’s text.                                  |
| `index`       | int    | 0‑based position within the file.                  |
| `char_offset` | int    | Starting character offset (Python code points).    |
| `char_length` | int    | Length in characters (same unit as `char_offset`). |

**Optional keys**

* `start_time` (float s) — written only when a timebase is known.
* Any extra metadata present in the original segment (e.g., `page`, `speaker`) is preserved.

> **Validation rule:** An implementation passes if every chunk contains the **mandatory subset** above; extra keys are allowed.

### 2.4 Querying by concept

Send a POST to `/indexes/file_chunks/search` using any Meilisearch vector or hybrid syntax.

* Home‑Index automatically stores each passage prefixed with `"passage: "`.
* For best recall, prefix the query string you send with `"query: "`.

`sort`, `limit`, `offset`, and all Meilisearch filters continue to work.

---

## 3 Minimal `docker-compose.yml`

```yaml
services:
  home-index:
    build: .
    environment:
      MODULES: |
        - name: text-module
      TOKENS_PER_CHUNK: 510
      CHUNK_OVERLAP: 50
      EMBED_MODEL_NAME: intfloat/e5-small-v2
      MEILISEARCH_HOST: http://meilisearch:7700
      TZ: America/Los_Angeles
    volumes:
      - ./input:/files:ro
      - ./output:/home-index
    depends_on: [meilisearch, text-module]

  meilisearch:
    image: getmeili/meilisearch:v1.15.2
    environment: [MEILI_NO_ANALYTICS=true, TZ=America/Los_Angeles]
    volumes:   [./output/meili:/meili_data]
    ports:     ["7700:7700"]

  text-module:
    build: ./text_module                 # emits content.json for each file
    environment:
      METADATA_DIRECTORY: /home-index/metadata
      QUEUE_NAME: text-module
      TZ: America/Los_Angeles
    volumes:
      - ./input:/files:ro
      - ./output:/home-index

  # Redis is OPTIONAL.  Add it only if your text-module uses queues.
```

---

## 4 Acceptance criteria (platform‑agnostic)

| #      | Scenario & pre‑conditions                                                                                          | Steps (user actions → expected result)                                                                                                                                                                                           |
| ------ | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1**  | **Initial build – existing files become searchable**<br>Stack starts with ≥ 1 file and a module that outputs text. | 1 Start stack → For each file, both `content.json` and `chunks.json` appear.<br>2 Issue a semantically re‑phrased query → Response contains at least one chunk whose `file_id` matches the file’s hash. ([test](tests/acceptance/test_s1.py)) |
| **2**  | **New file added while running**                                                                                   | 1 Copy a new file into `/files` → New `content.json` and `chunks.json` appear.<br>2 Concept query over the new content returns one of its chunks. ([test](tests/acceptance/test_s2.py))                                                                                |
| **3**  | **File contents change**                                                                                           | 1 Replace an existing file’s bytes (hash changes).<br>2 Wait → A new metadata directory (new hash) and new `chunks.json` are created; the old directory remains. ([test](tests/acceptance/test_s3.py))                                                                 |
| **4**  | **Chunk document schema is complete**                                                                              | 1 Open any produced `chunks.json` → Every object contains **all mandatory fields in § 2.3** with non‑null values; `start_time` may be absent; extra keys are permitted. ([test](tests/acceptance/test_s4.py))                                                          |
| **5**  | **Search results can be sorted & paged**                                                                           | 1 Search with<br>`"sort":["index:asc"], "limit":3, "offset":2"` → Hits are ordered by ascending `index`, beginning with logical chunk 3. ([test](tests/acceptance/test_s5.py))                                                                                         |
| **6**  | **Chunk size / overlap change triggers rebuild**                                                                   | 1 Stop stack; change `TOKENS_PER_CHUNK` *or* `CHUNK_OVERLAP`.<br>2 Restart → `/home-index/chunk_settings.json` reflects new values and the **mtime of every affected `chunks.json` increases**; chunk counts change accordingly. ([test](tests/acceptance/test_s6.py)) |
| **7**  | **Embed model change triggers re‑embedding only**                                                                  | 1 After a successful run, change `EMBED_MODEL_NAME` to another supported model and restart.<br>2 All `chunks.json` files are rewritten (new mtimes) **but every `content.json` remains byte‑identical**. ([test](tests/acceptance/test_s7.py))                         |
| **8**  | **Warm restart – settings unchanged**                                                                              | 1 Stop containers after success.<br>2 Restart with *identical* env vars → No `chunks.json` timestamps change; Meilisearch index receives no updates. ([test](tests/acceptance/test_s8.py))                                                                             |
| **9**  | **Deletion is reflected in the index (on restart or rescan)**                                                      | 1 Delete a file from `/files` **and restart the stack** (or invoke the project’s rescan endpoint).<br>2 Chunks linked to the removed file disappear from Meilisearch and from `output/metadata`. ([test](tests/acceptance/test_s9.py))                                 |
| **10** | **Hybrid search with filter returns correct subset**                                                               | 1 Run a hybrid search with `"filter":"module = 'text-module'"`.<br>2 Results include **only** chunks whose `module` equals `text-module`, still ranked by semantic relevance. ([test](tests/acceptance/test_s10.py))                                                    |

All scenarios MUST pass unchanged on Linux, macOS, and Windows (WSL).
