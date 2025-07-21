# ADR – F4 Modules enrich your project files

### 2025-07-21 Initial implementation
- Modules run in separate containers and communicate via Redis queues.
- Each module processes files then merges results into `document.json`.
- Order and unique IDs of modules are declared via environment variables.
- Runner loops queue archive-first jobs for mounted drives.
- Design keeps modules isolated and easily upgradeable.
