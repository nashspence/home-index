# f5 docs

## overview
[f4](../f4.md) modules may emit `content.json` for each file.
Home-index splits content into [*chunk*](../glossary.md#chunk)s and embeds them for concept search.

## settings
`TOKENS_PER_CHUNK`, `CHUNK_OVERLAP` and `EMBED_MODEL_NAME` control chunking and embedding.

## docker-compose
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
    volumes:
      - ./input:/files:ro
      - ./output:/home-index
    depends_on: [meilisearch, text-module]

  meilisearch:
    image: getmeili/meilisearch:v1.15.2
    environment: [MEILI_NO_ANALYTICS=true]
    volumes: [./output/meili:/meili_data]
```

See [meilisearch_file_chunk.schema.json](meilisearch_file_chunk.schema.json) and
[sample_chunk_document.json](sample_chunk_document.json) for schema and example.
