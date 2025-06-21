## 1 Principles

### 1.1 Hard Prohibitions  
- **NEVER** build dev- or release-containers, run acceptance tests, or `pip install -r requirements.txt` *locally*.  
- Work only with the libraries you need (run unit tests if present), then **push** and rely on CI.

---

## 2 Repository Layout
```text
repo/
├── features/                    # F1, F2, … (each with tests)
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
````

---

## 3 Features (`README.md`)

* Every **Fx** heading states a concise user goal as **“I want …”**.
* A bug must map to an existing **Fx**; otherwise add the feature or request clarification.

| Sub-heading         | Content                             |
| ------------------- | ----------------------------------- |
| **(1) Formal I/O**  | Exact input → output (symbolic OK)  |
| **(2) Explanation** | Same mapping in plain language      |
| **(3) Goal Fit**    | How it advances the “I want …” goal |

---

## 4 Testing

### 4.1 Acceptance Tests

* One `features/Fx/test/docker-compose.yml` per feature.
* Vary scenarios via **env vars** + **input files**; the test directory must contain **all inputs and capture all outputs**.
* Assert **exact user-facing output** (UI state, API responses, CLI logs, exit codes).
* Each test script **starts and stops** `<repo>:ci` via its compose file.
* On failure, **MUST** output all relevant release env container logs in addition to test failure logs.

### 4.2 Unit Tests (optional)

* Located in `tests/`.
* Executed by **`check.sh` inside the dev container** (local & CI).
* **Mock / stub / dummy everything** except (a) code under test and (b) Python built-ins.

### 4.3 Continuous Integration (`.github/workflows/test.yml`)

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

## 5 Release

### 5.1 Workflow (`.github/workflows/release.yml`)

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

### 5.2 Release Environment

* Maintain root-level **Dockerfile** and **docker-compose.yml**.
* Follow Docker best practices; keep images lean and secure.

---

## 6 Development

### 6.1 Prompt Classification

Classify prompt as one of: 
- **feature work (use §6.2)**
- **general maintenance (use §6.3)**
- **unclear** (ask).

### 6.2 Feature Work
1. Edit / add acceptance tests (unit tests optional).
2. Implement / fix code.
3. Run a full maintenance pass (§6.3 priorities 2-12) on the *affected feature code*
4. Run `agents-check.sh` (calls `check.sh`, linters **and** unit tests); fix issues.
5. Update **README.md §3 Features**.
6. Update adoption state of repo in README.md (§6.7)
7. **Push**.

### 6.3 General Maintenance

*(always exactly one focus per PR unless performing the mandated maintenance pass in 6.1-6)*

1. Until 100% explicit codebase: add the missing feature (§3) for an implicit code path.
2. Create / restructure / split files to match **§2 Repository Layout** exactly.
3. Optimise `test.yml` (§4.3).
4. Achieve passing acceptance tests (§4).
5. Complete feature docs (§3).
6. Optimise a feature’s I/O for its “I want …” goal.
7. Lean, up-to-date Docker & deps (§6.5).
8. Apply strict typing (§6.2).
9. Remove clutter.
10. Reach full unit-test coverage.
11. Add static docs (`docs/`).
12. Improve performance; target the Pareto frontier.

### 6.4 Style & Linting

* `check.sh` runs formatters / linters / type checkers **and** unit tests.
* Agents run `agents-check.sh` (installs deps, then `check.sh`) before every push.
* Enforce strict tools: ruff, mypy, Black + isort, ts (strict) + ESLint + Prettier, …

### 6.5 Dependencies

* Avoid `requirements.txt`, `package.json`, etc.
* Install dev deps via venv (or equivalent) in `postStart.sh`.
* Install runtime deps in the Dockerfile.
* Remove unused deps and **pin each dep to its exact latest release**.
* Keep containers as small as possible.

### 6.6 Development Environment (dev container)

* Located in `.devcontainer/`; base image **`cruizba/ubuntu-dind`**.
* Keep all dev-container files in sync.

### 6.7 Incremental Adoption

* Progress repo incrementally towards 100% accordance with this document - `AGENTS.md`. Maintain detailed record of the current state of this progression in `README.md` under the heading `Incremental Adoption`.

