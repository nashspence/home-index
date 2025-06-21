### 0 Hard Prohibitions

* **NEVER** build dev- or release-containers, run acceptance tests, or `pip install -r requirements.txt`.
* Work locally with only the libs you need; if unit tests exist, you may run them, but rely on CI after every **push**.

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
├── check.sh                  # lint / format **+ unit tests**
└── README.md
```

---

### 2 Features (`README.md`)

* Each **Fx** heading states a user goal as **“I want …”**.
* Bugs must map to an existing **Fx**; if none fits, add it or ask.

| Sub-heading         | Content                             |
| ------------------- | ----------------------------------- |
| **(1) Formal I/O**  | Exact input → output (symbolic OK)  |
| **(2) Explanation** | Same mapping in plain language      |
| **(3) Goal Fit**    | Why it promotes the “I want …” goal |

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

* Target a single template `features/Fx/test/docker-compose.yml`.
* Vary scenarios via **env vars** + **input files**; the test dir must hold **all inputs and capture all outputs**.
* Assert **exact user-facing output** (UI state, API response, CLI logs, exit codes).
* The test script **starts and stops** `<repo>:ci` via its compose file.

#### 4.2 Unit Tests (optional)

* Live in `tests/`.
* Executed by **`check.sh` inside the dev container** (CI and local).
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

      # dev container
      - run: docker-compose -f .devcontainer/docker-compose.yml up --build -d
      - run: docker exec ${REPO}-devcontainer poststart.sh
      - run: docker exec ${REPO}-devcontainer ./check.sh   # lint + unit tests

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

* `check.sh` → run formatters / linters **and** unit tests.
* Agents invoke `agents-check.sh` (installs `check.sh` deps, then `check.sh`) before every push.
* Keep linters strict (ruff, mypy, Black + isort, ESLint + Prettier, …).

---

### 7 Dependencies

* Install deps directly in Dockerfiles, do not use requirements.txt, package.json, etc.
* Remove unnecessary deps.
* Pin **every** dep to its exact latest release.

---

### 8 Dev Container (`.devcontainer/`)

Base image: `cruizba/ubuntu-dind`. Keep all dev-container files synced.

---

### 9 Release Environment

Maintain root-level **Dockerfile** and **docker-compose.yml** (follow Docker best practices).

---

### 10 Logging

Log enough detail to debug CI failures without interactive sessions.

---

### 11 Incremental Adoption

Phased strict typing, full re-org, etc.

---

### 12 Maintenance Priorities (one per PR)

1. Infer and list the implicit features behind code not covered by existing features.
2. Directory re-org complete.
3. Perfect `test.yml`.
4. Passing acceptance tests.
5. Complete a feature's docs (README §2).
6. Optimise a feature’s inputs & outputs to match its “I want …” goal**.
7. Lean, up-to-date Docker & deps.
8. Strict typing.
9. Remove clutter.
10. Full unit-test coverage.
11. Static docs (`docs/`).
12. Propose new use goal -> feature to add to features
