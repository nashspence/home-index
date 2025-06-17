## I. Conventions & Style Guidelines

1. **Language-specific formatting**

   * Adopt the community’s “strict” conventions (e.g. PEP 8 for Python, gofmt for Go, rustfmt for Rust, ESLint + Prettier for JS/TS).
   * Provide a top-level `check.sh` that runs linters/formatters with default settings—contributors **must** run this before pushing.

2. **Repository Layout**

   * One `features/` directory (see Feature Development below).
   * Shared libs in `lib/` or `shared/`.
   * CI configs under `.github/`.
   * Dev-container config under `.devcontainer/`.

---

## II. Development Environment Setup

1. **Dev Container**

   * **Base image**: `cruizba/ubuntu-dind:latest`.
   * In `.devcontainer/`:

     * `Dockerfile.devcontainer` (`FROM cruizba/ubuntu-dind:latest`)
     * `devcontainer.json` (points at `docker-compose.yml` + `postStart.sh`)
     * `docker-compose.yml` (v3 syntax; defines any additional dev services)
     * `postStart.sh` (initialization—e.g. install dependencies, build helpers)
   * Launch via **VS Code Remote – Containers** for a one-command “clone + open” experience.

2. **Local Docker-in-Docker**

   * Everything—including tests and builds—runs inside the dev container.
   * No local side-effects: you’re always running in the same Dockerized environment.

---

## III. Feature Development Workflow

1. **Atomic Features**

   * **Name**: Title Case, search-engine-friendly key phrase (e.g. `Generate Invoice PDF`).
   * **Scope**: One self-contained piece of functionality (per Atomic Design principles).
2. **Directory Structure**

   ```
   features/
     Generate Invoice PDF/
       src/…
       tests/…
   shared/…
   ```
3. **Integration-First Testing**

   * Every feature **must** include at least one *integration test* (no unit-only coverage).
   * Avoid mocks/stubs except when absolutely necessary—if used, annotate with a “why” comment.

---

## IV. Testing Strategy

1. **GitHub Actions (CI only)**

   * Trigger: **push** to any branch.
   * Workflow: `.github/workflows/test.yml`

     * Use a `docker-compose.ci.yml` to spin up the same environment.
     * **One job per feature**, named `Test: <Feature Name>`.
2. **Failure Reporting**

   * On any failure, CI must print:

     ```
     tests failed, see below:
     <relevant log snippet>
     ```

     (include full context to diagnose without rerunning).
3. **No Local Runs**

   * **Do not** run tests locally—always rely on CI’s container.
   * If you need to see failures, open a PR and I’ll relay the output.

---

## V. Logging & Observability

* Use **semantic/structured logging** (JSON, key/value).
* Follow the OpenTelemetry Logs Spec for field naming and levels.
* Logs should enable “logs-only” debugging (no stepping through code).

---

## VI. Documentation Requirements

1. **`README.md`**

   1. **Who**

      * Who benefits and why (rich, keyword-heavy).
   2. **Features**

      ```markdown
      [**Generate Invoice PDF**](features/Generate Invoice PDF/tests/test_invoice_pdf.py#L1-L20) — 
      Automatically generates a printable PDF invoice for finance managers.
      ```

      * Name tests after the feature (as close as possible).
      * Links jump to test code.
      * Description describes how it would help the person described in the **Who** section.
   3. **Contributions**

      * How to launch the dev container, run CI, open PRs, etc.
      * Reference VS Code Dev Containers docs for details.

---

## VII. CI/CD & Release Workflows

1. **`.github/workflows/release.yml`**

   * Trigger: on push where tags match vX.Y.Z (e.g. v1.2.3)
   * Build + push Docker images (using `secrets.DOCKER_{USERNAME,PASSWORD}`).
   * Tag & name per org conventions (e.g. `ghcr.io/org/repo:semver`).
   * Include full image reference in release notes.
   * Provide example `docker-compose.yml` for deployment.

---

## VIII. Maintenance & Continuous Improvement

1. **Test Refactoring**

   * Whenever possible, migrate any mock-heavy tests into real integration tests.
   * If a test can’t be migrated, leave a clear comment explaining *why* (and what would need to change).
2. **Environment Upkeep**

   * The Dockerfile is the *single source of truth* for runtime.
   * Feel free to install any dependencies—even large ones—to ensure parity with prod.
