## I. Formatting & Dependencies

1. **Code Style**

   * Use language’s **strict** formatter/linter (PEP 8, gofmt, rustfmt, ESLint + Prettier).
   * `check.sh` runs linters/formatters **and** dependency‐pin checks. **Run `./check.sh` and fix before every push.**

2. **Dependency Management**

   * **Pin** every dependency to an **exact** version in your manifest, using the **current latest** release.
   * **Manually verify** all version numbers are pinned and up‑to‑date before pushing.

---

## II. Dev Environment

1. **Dev Container**

   * **Base**: `cruizba/ubuntu-dind`.
   * Structure under `.devcontainer/`:

     * `Dockerfile.devcontainer` (`FROM cruizba/ubuntu-dind`)
     * `devcontainer.json` → vscode specific metadata
     * `docker-compose.yml` defines dev services & workspace mount
     * `postStart.sh` installs deps & builds helpers - always run on container first launch

2. **Usage**

   * Launch via VS Code Remote – Containers (“clone + open”).
   * **All** builds, tests, and Docker commands run *inside* this container—no host side‑effects.

---

## III. Features & Structure

1. **Atomic Features**

   * Folder under `features/` per feature in Title Case (e.g. `Generate Invoice PDF`).
   * Each feature contains:

     ```text
     features/
       <Feature Name>/
         src/
         tests/
         docker-compose.yml
     ```

2. **Shared Code**

   * Common code in `shared/`. Tested through the features that use it.

---

## IV. Testing & CI

1. **CI Pipeline**

   * **Trigger**: on **push** to any branch.
   * **Steps**:

     1. **Build & start the dev-container** using the `.devcontainer` compose file:

        ```bash
        docker-compose -f .devcontainer/docker-compose.yml up --build -d
        ```
     2. **Run and Wait** for `postStart.sh` to finish inside the container.
     3. **Inside** the running dev-container (via `docker exec` or Actions container steps):

        * **Build runtime image**:

          ```bash
          docker build -f Dockerfile -t repo-runtime:latest .
          ```
        * **Run per-feature tests**: one job per feature named `Test: <Feature Name>`:

          ```bash
          docker-compose -f features/<Feature Name>/docker-compose.yml up --abort-on-container-exit
          ```

          * Each feature’s compose file:

            * Starts/stops only its required services.
            * Defines its own bind mounts, environment variables, etc to provide controlled input/output scenario for testing

2. **Failure Reporting**

   * On any build or test failure, CI logs should strive to print a final summary in this form:

     ```text
     ci failed, see below:
     <relevant log snippet>
     ```

---

## V. Logging & Observability

* Logs alone must suffice to debug—no code stepping. Log everything you would need to handle test and build failures in the CI.

---

## VI. Documentation

1. **README.md** contains:

   * **Who & Why**: target users and benefits.
   * **Features**: list with links to their tests.
   * **Contributing**: clone → dev‑container → build → test → open PR.

---

## VII. Releases

* `.github/workflows/release.yml`:

  * **Trigger**: on tag `vX.Y.Z`.
  * Build & push Docker images (`secrets.DOCKER_{USERNAME,PASSWORD}`).
  * Tag per org convention (e.g. `ghcr.io/org/repo:semver`).
  * Update release notes with full image references.
  * Include example `docker-compose.yml` for deployment.

---

## VIII. Maintenance

* Additionally, try to stay on top of these:
  * **Refactor** non‑atomic code into feature folders.
  * **Migrate** mock‑heavy tests to integration tests—or document why mocks remain.
  * Keep both `Dockerfile` (runtime) and `Dockerfile.devcontainer` (dev) updated with all latest dependencies.
