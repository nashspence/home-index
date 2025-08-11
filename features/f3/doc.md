# f3 docs

## overview
Removable media mount under [*archive*](../glossary.md#archive).
Files remain searchable when drives unplug.

## markers
Each drive writes `<name>-status-ready` or `-status-pending` next to the drive.
Markers store last sync time and are never indexed.

## docker-compose
```yaml
services:
  home-index:
    image: ghcr.io/nashspence/home-index:latest
    environment: [ARCHIVE_DIRECTORY=/files/archive]
    volumes:
      - ./input:/files:ro
      - ./output:/home-index
    depends_on: [meilisearch]

  meilisearch:
    image: getmeili/meilisearch:latest
    environment: [MEILI_NO_ANALYTICS=true]
    volumes: [./output/meili:/meili_data]
```
