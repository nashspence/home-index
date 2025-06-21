### 0 Hard Prohibitions

* **NEVER** build dev- or release-containers, run acceptance tests, or `pip install -r requirements.txt`.
* Work locally with only the libs you need (run unit tests if present), then **push** and rely on CI.

---

### 1 Repository Layout

```text
repo/
├── features/                    # F1, F2, …
│   └── F?/test/                 # acceptance tests
│       └── docker-compose.yml
├── shared/                      # cross-feature code
├── tests/                       # unit tests (optional)
├── .devcontainer/
│   ├── Dockerfile.devcontainer
│   ├── devcontainer.json
│   ├── docker-compose.yml
│   └── postStart.sh
├── .github/workflows/
│   ├── test.yml                 # CI
│   └── release.yml              # Docker image release
├── Dockerfile                   # release build
├── docker-compose.yml           # release runtime
├── agents-check.sh
├── check.sh                     # lint / format **+ unit tests**
└── README.md
```

---

### 2 Features (`README.md`)

* Every **Fx** heading states a user goal as **“I want …”**.
* Bugs must map to an existing **Fx**; otherwise add the feature or request clarification.

| Sub-heading         | Content                             |
| ------------------- | ----------------------------------- |
| **(1) Formal I/O**  | Exact input → output (symbolic OK)  |
| **(2) Explanation** | Same mapping in plain language      |
| **(3) Goal Fit**    | How it advances the “I want …” goal |

---

### 3 Prompt → PR Workflow

1. Classify prompt → **feature**, **maintenance**, or **unclear** (ask).
2. Edit / add acceptance tests (unit tests optional).
3. Implement / fix code.
4. Update **README.md §2**.
5. Bump deps; resolve breakage.
6. Run `agents-check.sh` (runs `check.sh`, linters **and** unit tests); fix issues.
7. **Push**.

---

### 4 Tests

#### 4.1 Acceptance Tests

* One `features/Fx/test/docker-compose.yml`.
* Vary scenarios via **env vars** + **input files**; the test dir must contain **all inputs and capture all outputs**.
* Assert **exact user-facing output** (UI state, API responses, CLI logs, exit codes).
* Each test script **starts and stops** `<repo>:ci` via its compose file.

#### 4.2 Unit Tests (optional)

* Live in `tests/`.
* Executed by **`check.sh` inside the dev container** (local & CI).
* **Mock / stub / dummy everything** except (a) the code under test and (b) Python built-ins.

---

### 5 CI (`.github/workflows/test.yml`)

```yaml
name: test-features
on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    env:
      REPO: ${{ github.event.repository.name }}
      FEATURES: $(ls features | grep '^F')
    steps:
      - uses: actions/checkout@v4

      # Dev container
      - run: docker-compose -f .devcontainer/docker-compose.yml up --build -d
      - run: docker exec ${REPO}-devcontainer ./postStart.sh
      - run: docker exec ${REPO}-devcontainer ./check.sh   # lint + unit tests

      # Build release image for acceptance tests
      - run: docker exec ${REPO}-devcontainer \
             docker build -f Dockerfile -t ${REPO}:ci .

      # Acceptance tests
      - run: |
          set -euo pipefail
          for f in $FEATURES; do
            docker exec ${REPO}-devcontainer \
              pytest -q "features/${f}/test"
          done

      - run: docker-compose -f .devcontainer/docker-compose.yml down -v
```

---

### 6 Release Workflow (`.github/workflows/release.yml`)

A minimalist publish-on-GitHub-Release workflow using official Docker actions:

```yaml
name: release-image

on:
  release:
    types: [published]

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      # Log in to Docker Hub
      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      # Generate tags & labels (e.g. v1.2.3, latest)
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ secrets.DOCKER_USERNAME }}/${{ github.event.repository.name }}

      # Build and push the image
      - uses: docker/build-push-action@v4
        with:
          context: .
          platforms: linux/amd64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}

      # Show final tag(s) in the run summary
      - run: echo "${{ steps.meta.outputs.tags }}" >> $GITHUB_STEP_SUMMARY
```

---

### 7 Style & Linting

* `check.sh` ≤ formatters / linters **and** unit tests.
* Agents run `agents-check.sh` (installs deps, then `check.sh`) before every push.
* Enforce strict tools (ruff, mypy, Black + isort, ESLint + Prettier, …).

---

### 8 Dependencies

* Avoid `requirements.txt`, `package.json`, etc.
* Install dev deps using venv (or equivalent) directly in poststart.sh
* Install runtime deps directly in Dockerfile
* Remove unused deps and **pin every dep to its exact latest release.**

---

### 9 Dev Container (`.devcontainer/`)

Base image: `cruizba/ubuntu-dind`. Keep all dev-container files in sync.

---

### 10 Release Environment

Maintain root-level **Dockerfile** and **docker-compose.yml** (follow Docker best practices).

---

### 11 Logging

Emit logs sufficient to diagnose CI failures without interactive sessions.

---

### 12 Incremental Adoption

Progressively move toward strict typing, full re-org, etc.; record gaps in **README.md**.

---

### 13 Maintenance Priorities (one focus per PR)

1. Add missing feature & docs for implicit code paths.
2. Restructure / extract modules to match target layout.
3. Optimise `test.yml`.
4. Achieve passing acceptance tests.
5. Complete feature docs (README §2).
6. Optimise a feature’s inputs ↔ outputs to its “I want …” goal.
7. Lean, up-to-date Docker & deps.
8. Apply strict typing.
9. Remove clutter.
10. Reach full unit-test coverage.
11. Add static docs (`docs/`).
12. Improve Perf: target Pareto frontier
    
