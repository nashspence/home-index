### 0 Hard Prohibitions

* **NEVER** build dev- or release-containers, run acceptance tests, `pip install -r …`, `pytest -q`, etc.
* Work locally with only the libraries you need; rely on CI after every **push**.

---

### 1 Repository Layout

```text
repo/
├── features/                 # F1, F2, …
│   └── F?/test/              # acceptance tests
│       └── docker-compose.yml
├── shared/                   # cross-feature code
├── tests/                    # unit tests (optional)
├── .devcontainer/
│   ├── Dockerfile.devcontainer
│   ├── devcontainer.json
│   ├── docker-compose.yml
│   └── postStart.sh
├── .github/workflows/
│   └── test.yml
├── Dockerfile                # release build
├── docker-compose.yml        # release runtime
├── agents-check.sh
├── check.sh                  # lint / format
└── README.md
```

---

### 2 Features (`README.md`)

* Each **Fx** title is a user goal written as **“I want …”**.
* Bugs must map to an existing **Fx**; if none fits, add it or ask for clarification.

| Sub-heading         | Content                                    |
| ------------------- | ------------------------------------------ |
| **(1) Formal I/O**  | Exact input → output mapping (symbolic OK) |
| **(2) Explanation** | Same mapping in plain language             |
| **(3) Goal Fit**    | Why it fulfils the “I want …” goal         |

---

### 3 Prompt → PR Workflow

1. Classify prompt → **feature**, **maintenance**, or **unclear** (ask).
2. Edit / add acceptance tests (unit tests optional).
3. Implement / fix code.
4. Update **README.md §2**.
5. Bump deps; resolve breakage.
6. Run `agents-check.sh`; fix issues.
7. **Push**.

---

### 4 Tests

#### 4.1 Acceptance Tests

* One `features/Fx/test/docker-compose.yml`.
* Vary scenarios with **env vars** + **input files**; the test dir must hold **all inputs and capture all outputs**.
* Assert the **exact user-facing output** (UI state, API response, CLI logs, exit codes).
* Each test script **starts and stops** `<repo>:ci` via its compose file.

#### 4.2 Unit Tests (optional)

* Live under `tests/`.
* Run **inside the dev container**.
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
      REPO: "<repo>"
      FEATURES: $(ls features | grep '^F')
    steps:
      - uses: actions/checkout@v4

      # dev container
      - run: docker-compose -f .devcontainer/docker-compose.yml up --build -d
      - run: docker exec ${REPO}-devcontainer ./check.sh

      # unit tests
      - run: |
          if [ -d tests ]; then
            docker exec ${REPO}-devcontainer pytest -q tests
          fi

      # build release image for acceptance tests
      - run: docker exec ${REPO}-devcontainer \
             docker build -f Dockerfile -t ${REPO}:ci .

      # acceptance tests per feature
      - run: |
          set -euo pipefail
          for f in $FEATURES; do
            docker exec ${REPO}-devcontainer \
              pytest -q "features/${f}/test"
          done

      - run: docker-compose -f .devcontainer/docker-compose.yml down -v
```

---

### 6 Style & Linting

* Humans: run `check.sh` in the dev container.
* Agents: run `agents-check.sh` before **push** (installs deps, then `check.sh`).
* Keep linters strict (ruff, mypy, Black + isort, ESLint + Prettier, …).

---

### 7 Dependencies

Pin **every** dependency to the exact latest release.

---

### 8 Dev Container (`.devcontainer/`)

* Base: `cruizba/ubuntu-dind`.
* Keep **Dockerfile.devcontainer**, **devcontainer.json**, **docker-compose.yml**, **postStart.sh** in sync.

---

### 9 Release Environment

Maintain root-level **Dockerfile** + **docker-compose.yml** (follow Docker best practices).

---

### 10 Logging

Emit logs sufficient to debug CI failures without interactive sessions.

---

### 11 Incremental Adoption

Strict typing, full re-org, etc. may be phased; note any remaining gaps in **README.md**.

---

### 12 Maintenance Priorities (one per PR)

1. **Optimise each feature’s inputs & outputs to match its “I want …” goal**.
2. Rich per-feature docs (README §2).
3. Perfect `test.yml`.
4. Directory re-org complete.
5. Passing acceptance tests.
6. Lean, up-to-date Docker & deps.
7. Strict typing.
8. Remove clutter.
9. Full unit-test coverage.
10. Static docs (`docs/`).
