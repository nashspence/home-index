## INDEX

```
S0_HARD_PROHIBITIONS
S1_EXPECTED_PROMPT_FLOW
S2_REPOSITORY_ARTIFACTS_REFERENCE
S3_TESTING
S4_DEVELOPMENT_ENVIRONMENT
S5_MAINTENANCE
S6_RELEASE
```

---

## S0\_HARD\_PROHIBITIONS

* MUST\_NOT modify any feature spec at `features/Fx/SPEC.md` unless directly prompted.
* MUST\_NOT build dev‑ or release‑containers or run acceptance tests locally.
* MUST\_NOT commit without running check.sh and fixing any warnings / errors.

---

## S1\_SERVICING_A_PROMPT

### S1.1\_EXPECTED\_FLOW

1. Read relevant feature specs (`features/Fx/SPEC.md`) if they exist (see S2.2).
2. Make changes to specs if directed by the prompt (see S2.2).
3. Edit / add prompt indicated acceptance test skeletons as per spec (see S3.2).
4. Implement / fix prompt indicated code as per spec.
5. Add / update full unit test coverage for any added / modified code (see S3.2).
6. Finish any unfinished relevant acceptance tests as per spec (see S3.1).
7. Maintenance (see S5).
8. PUSH, open PR.

*If the prompt is vague, ask clarifying questions. DO\_NOT change code.*

### S1.2\_SPECIAL_PROMPTS

- If the prompt contains just a URL that matches /^https:\/\/productionresultssa\d+\.blob\.core\.windows\.net\/actions-results\/.*$/ (PCRE‑style) then assume that URL is a link to a text file that contains raw Github Actions CI logs from a failed CI run. Download the file, analyse the logs to determine the reason for the failure, and fix the issue. It is most likely a failing CI step related to recent changes on your current branch.

---

## S2\_REPOSITORY\_ARTIFACTS\_REFERENCE

### S2.1\_FEATURES\_LIST

* Location: README.md → Features section.
* Simple ordered list of feature titles `Fx <name>` linked to corresponding `features/Fx/SPEC.md`.

### S2.2\_FEATURE\_SPECIFICATIONS

* One markdown file per feature in `features/Fx/`, named `SPEC.md`.
* Contains an `Acceptance` section - which is always the master feature specification.
* Always link each `Acceptance` scenario to corresponding acceptance test files.
* Always match existing format and style when editing.

### S2.3\_REPOSITORY\_LAYOUT

```text
repo/
├── features/ F1,F2,…
│   └── F?/
│       ├── SPEC.md
│       ├── ADR.md
│       ├── tests/acceptance/docker-compose.yml
│       └── tests/unit/
├── shared/
├── tests/
├── .devcontainer/(Dockerfile.devcontainer, devcontainer.json, docker-compose.yml, postStart.sh, install_dev_tools.sh)
├── .github/workflows/(test.yml, release.yml)
├── Dockerfile
├── docker-compose.yml
├── check.sh
└── README.md
```

### S2.4_ADR_FILES

* Every feature directory `features/Fx/` maintains `ADR.md`.
* Record important implementation details chronologically.
* Append new notes instead of rewriting old ones.
* Use `### YYYY-MM-DD` headings for entries.

---

## S3\_TESTING

### S3.1\_ACCEPTANCE\_TESTS

* Docker is **ABSOLUTELY NECESSARY** to run the acceptance tests. Do not even try without it.
* Acceptance test script starts & stops `<repo>:ci` via compose.
* ONE `features/Fx/tests/acceptance/docker-compose.yml` per feature.
* Keep all inputs/outputs in `features/Fx/tests/acceptance/{input,output}` dirs.
* Handle each acceptance scenario from the spec via env vars + input files
* Each acceptance scenario lives in `features/Fx/tests/acceptance/test_sY.py` with a function named `test_fXsY`.
* Assert exact user‑facing output, exactly as spec'd (logs, UI, API, exit codes).
* Do NOT use mocks, stubs, or dummies unless absolutely necessary.
* On failure output test logs + relevant release‑env container logs.

### S3.2\_UNIT\_TESTS (optional)

* Location: `tests/` for shared code or `features/Fx/tests/unit/` for feature code.
* Executed by `check.sh` inside dev container (local & CI).
* Mock / stub / dummy everything except (a) code under test (b) Python built‑ins.
* Always strive for complete coverage.

### S3.3\_CONTINUOUS\_INTEGRATION

* Workflow file: .github/workflows/test.yml.
* Reference https://raw.githubusercontent.com/nashspence/codex-agentmd/refs/heads/main/test.yml.

### S3.4\_TEST\_ENVIRONMENT

* All tests run in dev‑container image S4.2.

---

## S4\_DEVELOPMENT\_ENVIRONMENT

### S4.1\_STYLE\_AND\_LINTING

* `check.sh` installs deps then runs formatters, linters, type-checkers + unit tests; MUST run before every push.
* Use strictest toolchain possible: ruff, mypy, black, isort, TypeScript(strict)+ESLint+Prettier.

### S4.2\_DEV\_CONTAINER

* Location: .devcontainer/; base image `cruizba/ubuntu-dind`.

### S4.3\_DEPENDENCIES

* Avoid manifest files.
* Dev system deps → install Dockerfile.devcontainer.
* Dev import deps → install via venv in postStart.sh.
* All runtime deps → install in root-level Dockerfile.
* Remove unused deps
* Pin each dep to exact latest release.
* Follow Docker best practices; keep images lean & secure.

---

## S5\_MAINTENANCE

Double check all of the following:

```
STRUCTURE      → repo layout (S2.3)
ACCEPT_TESTS   → optimal I/O + tests (S3.1)
DOCS           → update docs (S2.2)
DOCKER_DEPS    → lean Docker & deps (S4.3)
TYPING         → strict typing (S4.1)
CLEANING       → remove dead code / files, refactor
UNIT_COVERAGE  → full unit‑test coverage (S3.2)
PERFORMANCE    → optimise
ADR_HISTORY    → maintain features/Fx/ADR.md
```

---

## S6\_RELEASE

### S6.1\_RELEASE\_WORKFLOW

* Automated by .github/workflows/release.yml.
* Reference https://raw.githubusercontent.com/nashspence/codex-agentmd/refs/heads/main/release.yml.

### S6.2\_RELEASE\_ENVIRONMENT

* Maintain root Dockerfile & docker-compose.yml. Keep images lean, minimal, secure.
