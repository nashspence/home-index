# f6 docs

## overview
The [*api*](../glossary.md#api) exposes WebDAV and JSON endpoints for file ops under [*files*](../glossary.md#files).

## notes
Paths are relative to [*files*](../glossary.md#files).
Metadata lives under `metadata/by-id/<hash>/document.json`.
Changes debounce ~2 s before updating [*doc*](../glossary.md#doc) and [*search host*](../glossary.md#search-host).

## docker-compose
```yaml
services:
  home-index:
    image: ghcr.io/nashspence/home-index:latest
    volumes:
      - ./input:/files:rw
      - ./output:/home-index
    ports: ["8000:8000"]
    depends_on: [meilisearch]

  meilisearch:
    image: getmeili/meilisearch:v1.15
    environment: [MEILI_NO_ANALYTICS=true]
    volumes: [./output/meili:/meili_data]
```
