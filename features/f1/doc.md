# f1 docs

## overview
Scheduled scans crawl [*files*](../glossary.md#files) and write [*meta*](../glossary.md#meta).
The service sleeps between [*cron*](../glossary.md#cron) ticks.

## configuration
Set `CRON_EXPRESSION` to any 5 or 6 field [*cron*](../glossary.md#cron) (default `0 2 * * *`).
Zone follows `TZ`.

## docker-compose
```yaml
services:
  home-index:
    image: ghcr.io/nashspence/home-index:latest
    environment: [CRON_EXPRESSION=* * * * *]
    volumes:
      - ./input:/files:ro
      - ./output:/home-index
    depends_on: [meilisearch]

  meilisearch:
    image: getmeili/meilisearch:latest
    environment: [MEILI_NO_ANALYTICS=true]
```
