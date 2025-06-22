## 1 Principles

### 1.1 Hard Prohibitions
- **NEVER** deviate from §6.1 Handling a Prompt.
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

## 3 Features

### 3.1 Canonical List
* Listed under `Features` in README.md.
* Each feature has an **Fx** designation - ex. F1 - and a title that is a concise *user goal* in the form **“I want …”** - ex. F1 "I want to preview my work before commit.". Together, goals should describe a *consistent, informed, domain-aware user*.
* Links to static documentation (§3.2).

### 3.2 Feature Documentation

In `docs` directory, one file per feature. Conform strongly to this example [`docs/F1`](https://raw.githubusercontent.com/nashspence/codex-agentmd/refs/heads/main/Fx.md):

- Value section **MUST** match length, tone, and of the example to describe WHY the feature helps the user's goal.
- Specification **MUST** match example form and describe a passing acceptance test.
- Vocabulary **MUST** be **EXACTLY** the inputs and outputs the user will interact with.
- Include Helper section iff it is necessary.


---

## 4 Testing

### 4.1 Acceptance Tests

* One `features/Fx/test/docker-compose.yml` per feature.
* Vary scenarios via **env vars** + **input files**; the test directory must contain **all inputs and capture all outputs**.
* Assert **EXACT user-facing output** (UI state, API responses, CLI logs, exit codes).
* Each test script **starts and stops** `<repo>:ci` via its compose file.
* On failure, **MUST** output all relevant release env container logs in addition to test failure logs.

### 4.2 Unit Tests (optional)

* Located in `tests/`.
* Executed by **`check.sh` inside the dev container** (local & CI).
* **Mock / stub / dummy everything** except (a) code under test and (b) Python built-ins.

### 4.3 Continuous Integration

Infer from this example [`.github/workflows/test.yml`](https://raw.githubusercontent.com/nashspence/codex-agentmd/refs/heads/main/test.yml).

### 4.4 Test Environment

See §6.4.

---

## 5 Release

### 5.1 Workflow

Infer from this example [`.github/workflows/release.yml`](https://raw.githubusercontent.com/nashspence/codex-agentmd/refs/heads/main/release.yml).

### 5.2 Release Environment

* Maintain root-level **Dockerfile** and **docker-compose.yml**.
* Follow Docker best practices; keep images lean and secure.

---

## 6 Development

### 6.1 Handling a Prompt

Classify prompt as either Feature Work, Maintenance Work, or Unclear and proceed as the corresponding section says.

#### 6.1.1 Feature Work

Has an inferrable target feature. For example, "Fix bug on F1", "Implement F2".
  
Create the PR as follows:

  1. Edit / add acceptance tests (unit tests optional) (§4).
  2. Implement / fix code.
  3. Run a full maintenance pass on the *affected feature code*. (§6.5: address priorities 2-12)
  4. Run `agents-check.sh`; fix issues. (§6.2)
  5. Update docs. (§3.2)
  6. Update `Planned Maintenance`. (§6.5)
  7. **Push**.
         
#### 6.1.2 Maintenance Work

No inferrable target feature. For example, "Do maintenance.", "Clean up the repo.".
  
Create the PR as follows:

  1. Check `Planned Maintenance`. 
  2. Resolve one item from `Planned Maintenance`. If there is no planned maintanance items, do a **deep scan** of the repo to locate and prioritize tasks, and skip straight to step 4. (§6.5)
  3. Run `agents-check.sh`; fix issues. (§6.2)
  4. Update `Planned Maintenance`. (§6.5)
  5. **Push**.
         
#### 6.1.3 Unclear

Do not create a PR. Clarify.

### 6.2 Style & Linting

* `check.sh` runs formatters / linters / type checkers **and** unit tests.
* Agents run `agents-check.sh` (installs deps, then `check.sh`) before every push.
* Enforce strict tools: ruff, mypy, Black + isort, ts (strict) + ESLint + Prettier, …

### 6.3 Dependencies

* Avoid `requirements.txt`, `package.json`, etc.
* Install dev deps via venv (or equivalent) in `postStart.sh`.
* Install runtime deps in the Dockerfile.
* Remove unused deps and **pin each dep to its exact latest release**.
* Follow Docker best practices; keep images lean and secure.

### 6.4 Development Environment (dev container)

* Contained in `.devcontainer/`; base image **`cruizba/ubuntu-dind`**.
* Maintain a clean conventional vscode dev-container.

### 6.5 Incremental Adoption

Progress repo incrementally towards 100% accordance with this document. `README.md` under the heading `Planned Maintenance`, update a prioritized list of tasks to fix with **everything** you know is **not** in accordance with `AGENTS.md` any time you push. Use the following ordered list as the priority heuristic:

  1. Ensure features are clean, managable, and cover **100%** of existing code - if not, add, remove, rename, etc. (§3.1)
  2. Create / restructure / split files to match repo expectations. (§2)
  3. Optimise `test.yml` (§4.3).
  4. Achieve passing acceptance tests (§4.1).
  5. Perfect static docs (`docs/`). (§3.2)
  6. Optimise a feature’s I/O for its “I want …” goal. (§3.1)
  7. Lean, up-to-date Docker & deps (§6.3).
  8. Apply strict typing (§6.2).
  9. Remove unnecessary file and code. Refactor code to conform to community conventions.
  10. Reach full unit-test coverage. (§4.2)
  11. Improve performance; target the Pareto frontier.



