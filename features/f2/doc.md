# f2 docs

## overview
One [*doc*](../glossary.md#doc) exists per unique bytes under [*files*](../glossary.md#files).
Duplicate paths point to the same [*doc*](../glossary.md#doc).

## rebuild
The scheduled sync from [f1](../f1.md) walks [*files*](../glossary.md#files) and maintains
[*hashes*](../glossary.md#hashes) and [*paths*](../glossary.md#paths).
New copies increment `copies`; deletions decrement it.

## docker-compose
```yaml
services:
  home-index:
    image: ghcr.io/nashspence/home-index:latest
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

See [meilisearch_document.schema.json](meilisearch_document.schema.json) and
[sample_document.json](sample_document.json) for schema and example.
