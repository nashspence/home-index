## INDEX

```
S0_HARD_PROHIBITIONS
S1_PROMPT_CLASSIFICATION_AND_FLOW
S2_REPOSITORY_ARTIFACTS_REFERENCE
S3_TESTING
S4_DEVELOPMENT_ENVIRONMENT
S5_MAINTENANCE_PASS
S6_PUSH_CI_RELEASE
S7_OPEN_PR
```

---

## S0\_HARD\_PROHIBITIONS

* MUST\_NOT deviate from S1\_PROMPT\_CLASSIFICATION\_AND\_FLOW.
* MUST\_NOT modify any feature spec at `docs/Fx.md` unless prompt indicates GOAL_WORK (S1.1).
* MUST\_NOT build dev‑ or release‑containers, run acceptance tests, or `pip install -r requirements.txt` locally.
* Work only with required libraries, run unit tests if present, then PUSH and rely on CI.

---

## S1\_PROMPT\_CLASSIFICATION\_AND\_FLOW

Input prompt MUST be classified into exactly ONE of the categories, then the matching workflow MUST be executed in order.

```
CATEGORIES:
  GOAL_WORK
  FEATURE_WORK
  MAINTENANCE_WORK
  UNCLEAR
```

### S1.1\_GOAL\_WORK  ("Tighten acceptance on F1", "Revise F2 docs")

1. Read relevant feature specs (`docs/Fx.md`).
2. Make changes to specs as per prompt - do not change code.
3. Update Features list in README.md if needed.
4. Update Planned\_Maintenance in README.md with an appropriate `conform to new spec` item (S5.2).
5. PUSH, open PR.

### S1.2\_FEATURE\_WORK  ("Fix bug on F1", "Implement F2")

1. Read relevant feature specification (`docs/Fx.md`, section `Acceptance`).
2. Implement / fix code as per spec
3. Edit / add acceptance tests as per spec
4. Update Planned\_Maintenance in README.md (S5.2).
5. PUSH, open PR.

### S1.3\_MAINTENANCE\_WORK  ("Refactor repo", "Do maintenance")

1. If Planned\_Maintenance not empty → pick & resolve ONE item; else deep‑scan repo, create tasks, resolve ONE.
2. Run `agents-check.sh`; fix issues S4.1.
3. Update Planned\_Maintenance S5.2.
4. PUSH, open PR.

### S1.4\_UNCLEAR

Ask clarifying questions. DO\_NOT open PR.

---

## S2\_REPOSITORY\_ARTIFACTS\_REFERENCE

### S2.1\_FEATURES\_LIST

* Location: README.md → Features section.
* List describes a consistent, domain‑aware user.
* Each entry links to `docs/Fx.md`.

### S2.2\_FEATURE\_SPECIFICATIONS

* One markdown file per feature in `docs/`, named `Fx.md`.

### S2.3\_REPOSITORY\_LAYOUT

```text
repo/
├── features/ F1,F2,…
│   └── F?/test/docker-compose.yml
├── shared/
├── tests/
├── .devcontainer/(Dockerfile.devcontainer, devcontainer.json, docker-compose.yml, postStart.sh)
├── .github/workflows/(test.yml, release.yml)
├── Dockerfile
├── docker-compose.yml
├── agents-check.sh
├── check.sh
└── README.md
```

---

## S3\_TESTING

### S3.1\_ACCEPTANCE\_TESTS

* ONE `features/Fx/test/docker-compose.yml` per feature.
* Vary scenarios via env vars + input files; keep all inputs/outputs in test dir.
* Assert exact user‑facing output, exactly as spec'd (logs, UI, API, exit codes).
* Test script starts & stops `<repo>:ci` via compose.
* On failure output test logs + relevant release‑env container logs.

### S3.2\_UNIT\_TESTS (optional)

* Location: tests/.
* Executed by `check.sh` inside dev container (local & CI).
* Mock / stub / dummy everything except (a) code under test (b) Python built‑ins.

### S3.3\_CONTINUOUS\_INTEGRATION

* Workflow file: .github/workflows/test.yml.
* Reference https://raw.githubusercontent.com/nashspence/codex-agentmd/refs/heads/main/test.yml.

### S3.4\_TEST\_ENVIRONMENT

* All tests run in dev‑container image S4.2.

---

## S4\_DEVELOPMENT\_ENVIRONMENT

### S4.1\_STYLE\_AND\_LINTING

* `check.sh` runs formatters, linters, type‑checkers + unit tests.
* `agents-check.sh` installs deps then calls `check.sh`; MUST run before every push.
* Strict toolchain: ruff, mypy, black, isort, TypeScript(strict)+ESLint+Prettier.

### S4.2\_DEV\_CONTAINER

* Location: .devcontainer/; base image `cruizba/ubuntu-dind`.

### S4.3\_DEPENDENCIES

* Avoid manifest files.
* Dev deps → install via venv in postStart.sh.
* Runtime deps → install in root-level Dockerfile.
* Remove unused deps; pin each dep to exact latest release.
* Follow Docker best practices; keep images lean & secure.

---

## S5\_MAINTENANCE\_PASS

Priority order:

```
1 STRUCTURE      → repo layout (S2.3)
2 ACCEPT_TESTS   → optimal I/O + tests (S3.1)
3 DOCS           → update docs (S2.2)
4 DOCKER_DEPS    → lean Docker & deps (S4.3)
5 TYPING         → strict typing (S4.1)
6 CLEANING       → remove dead code / files, refactor
7 UNIT_COVERAGE  → full unit‑test coverage (S3.2)
8 PERFORMANCE    → optimise
```

### S5.2\_PLANNED\_MAINTENANCE\_QUEUE

* Location: README.md → Planned\_Maintenance section.
* Update on every push.
* Always remove completed/irrelevant items.

---

## S6\_RELEASE

### S6.1\_RELEASE\_WORKFLOW

* Automated by .github/workflows/release.yml.
* Reference https://raw.githubusercontent.com/nashspence/codex-agentmd/refs/heads/main/release.yml.

### S6.2\_RELEASE\_ENVIRONMENT

* Maintain root Dockerfile & docker-compose.yml. Keep images lean, minimal, secure.

---

## S7\_OPEN\_PR

1. Confirm workflow for prompt category (S1) completed.
2. Ensure Planned\_Maintenance is current.
3. Open PR.
