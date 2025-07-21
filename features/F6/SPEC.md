# F6 Remote file operations via API

## 1 Why a file‑operations API?

Many users work on laptops, tablets, or servers where mounting the full project
directory is awkward or impossible. F6 exposes a lightweight HTTP service so
remote scripts or GUI clients can **upload, move, rename, and delete files**.
After each change Home‑Index refreshes its metadata store and Meilisearch index
almost immediately, so searches stay up‑to‑date between scheduled scans.

---

## 2 How it works

Uploads, renames, and deletes all ride on a single WebDAV share:

```bash
# PUT / create
curl -T ./docs/note.txt http://localhost:8000/dav/docs/note.txt

# MOVE / rename
curl -X MOVE -H 'Destination: http://localhost:8000/dav/archive/note.txt' \
     http://localhost:8000/dav/docs/note.txt

# DELETE
curl -X DELETE http://localhost:8000/dav/archive/note.txt
```

For programmatic batching there is also a JSON endpoint:

```json
POST /fileops
{
  "move":   [{ "src": "docs/note.txt", "dest": "archive/note.txt" }],
  "delete": ["old.txt"]
}
```

* **Path roots** All paths are **relative to `INDEX_DIRECTORY`**
  (default `/files` inside the container).

* **Metadata layout** Each file’s metadata lives at
  `{$INDEX_DIRECTORY}/metadata/by-id/<hash>/document.json`.

* **Index latency** Changes are debounced for ≈ **2 s**; after that the metadata
  file is written and Meilisearch is updated—no full rescan required.

* **Port selection** The service listens on
  `FILE_API_PORT` (**default `8000`**).
  Expose any host port you like via Docker or Podman.

WebDAV clients such as Finder, Nautilus, Windows Explorer, `davfs2`, or
`rclone` therefore work out‑of‑the‑box; you only need the JSON API when you
prefer explicit batched operations.

---

## 3 Minimal `docker-compose.yml`

```yaml
services:
  home-index:
    image: ghcr.io/nashspence/home-index:latest     # or build: .
    environment:
      - CRON_EXPRESSION=* * * * *                  # periodic rescan
    volumes:
      - ./input:/files:rw                          # project + metadata
      - ./output:/home-index                       # logs, cache, etc.
    ports:
      - "8000:8000"                                # map FILE_API_PORT
    depends_on: [meilisearch]

  meilisearch:
    image: getmeili/meilisearch:v1.15
    environment:
      - MEILI_NO_ANALYTICS=true
    volumes:
      - ./output/meili:/meili_data
```

---

## 4 Acceptance criteria

| #     | Scenario & pre‑conditions                                      | Steps (user actions → expected behaviour)                                                                                                                                                                 |
| ----- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1** | **Add a file**<br>Stack running and WebDAV endpoint reachable. | 1 `curl -T ./a.txt http://localhost:8000/dav/a.txt` → `input/metadata/by-id/<hash>/document.json` exists **and** searching for that `id` returns a document without waiting for a cron tick. ([test](acceptance_tests/s1.py)) |
| **2** | **Move a file (JSON)**                                         | 1 After Scenario 1 POST<br>`{"move":[{"src":"a.txt","dest":"b.txt"}]}` to `/fileops` → Document’s `paths` contain `b.txt` and no longer include `a.txt`; search results show the new path within seconds. ([test](acceptance_tests/s2.py)) |
| **3** | **Delete a file**                                              | 1 POST `{"delete":["b.txt"]}` to `/fileops` → Document disappears from both metadata store and search index. ([test](acceptance_tests/s3.py)) |
| **4** | **Batch operations**                                           | 1 Upload two files via `/dav` then POST a single body<br>`{"move":[{"src":"c.txt","dest":"e.txt"}], "delete": ["d.txt"]}` → All changes reflected correctly after the response. ([test](acceptance_tests/s4.py)) |
| **5** | **Rename via WebDAV**                                          | 1 `curl -X MOVE -H 'Destination: http://localhost:8000/dav/f.txt' http://localhost:8000/dav/e.txt` → Same results as Scenario 2, proving that WebDAV MOVE is equivalent to the JSON `move`. ([test](acceptance_tests/s5.py)) |

All scenarios **must pass unchanged** on Linux, macOS, and Windows (WSL).
