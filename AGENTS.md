## I. Formatting & Dependencies

1. **Code Style**

   * Use language’s **strict** formatter/linter (PEP 8, gofmt, rustfmt, ESLint + Prettier).
   * Humans use `check.sh` to run linters/formatters in the dev container. Help maintain this file, but **do not run it**.
   * Agents use `agents-check.sh` to run linters/formatters. This version should also install all necessary dependencies for `agents-check.sh` to work. **Run `agents-check.sh` before every push and fix any problems**

2. **Dependency Management**

   * **Pin** every dependency to an **exact** version, using the **current latest** release.
   * **Manually verify** all version numbers are pinned and up‑to‑date before pushing.
  
---

## II. Dev Environment

1. **Dev Container**

   * **Base**: `cruizba/ubuntu-dind`.
   * Structure under `.devcontainer/`:

     * `Dockerfile.devcontainer` (`FROM cruizba/ubuntu-dind`)
     * `devcontainer.json` → vscode specific metadata, help maintain it correctly
     * `docker-compose.yml` defines dev services & workspace mount
     * `postStart.sh` installs deps & builds helpers - always run on container first launch

2. **Usage**

   * Humans launch via VS Code Remote – Containers (“clone + open”).
   * Humans run **All** builds, tests, and Docker commands *inside* this container.
   * Agents do not run the container, builds, tests, etc. They push and await for a human to relay feedback from the CI.

---

## III. Features & Structure

1. **Atomic Features**

   * Folder under `features/` per feature in snake case (e.g. `generate_invoice_pdf`).

   * Each feature contains:

     ```text
     features/
       <feature_name>/
         src/
           example_module.py
         test/
           docker-compose.yml  # sample env vars
           example_test.py
           input/    # sample input files
           output/   # expected outputs for test assertions
     ```

   * **Testing Standards**:

     * All tests should use the Docker-in-Docker (DinD) setup.
     * Tests must be **fully integrated**, meaning they:

       * Run the runtime container (`Dockerfile`) with their own pre-defined inputs (e.g. env vars, bind-mount files) supplied from the dev/test container (`Dockerfile.devcontainer`).
       * Assert expected outputs.
     * If full integration is **not possible** for a feature:

       * A comment must explain the limitation.
       * The test code should be bind-mounted into the runtime container and executed via a separate entrypoint that:

         * Installs any test-specific dependencies.
         * Runs the tests.

2. **Shared Code**

   * Common code in `shared/`. Tested through the features that use it.

---

## IV. Testing & CI

1. **Github Actions (CI Pipeline)**

   * **Trigger**: on **push** to any branch.
   * **Steps**:

     1. **Build & start the dev-container** using the `.devcontainer` compose file:

        ```bash
        docker-compose -f .devcontainer/docker-compose.yml up --build -d
        ```
     2. **Run and Wait** for `postStart.sh` to finish inside the container.
     3. **Inside** the running dev-container (via `docker exec` or Actions container steps):
        * **Run `check.sh`
        * **Build runtime image**:

          ```bash
          docker build -f Dockerfile -t repo-runtime:latest .
          ```
        * **Run per-feature tests**: use a strategy across a matrix of features `Test: <Feature Name>`:

          ```bash
          docker-compose -f features/<Feature Name>/docker-compose.yml up --abort-on-container-exit
          ```

2. **Failure Reporting**

   * On any build or test failure, CI logs should strive to print a final summary in this form. Human will relay this back exactly on failure:

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

   * **Who & Why**: target users and benefits, be extremely logical rather than rhetorical.
   * **Features**: list with links to their tests.
   * **Contributing**: clone → dev‑container → build → test → open PR.
   * anything else that the agent deems relevant

---

## VII. Releases

* `.github/workflows/release.yml`:

  * **Trigger**: on tag `vX.Y.Z`.
  * Build & push Docker images (`secrets.DOCKER_{USERNAME,PASSWORD}`).
  * Tag per org convention (e.g. `ghcr.io/org/repo:semver`).
  * Update release notes with full image references.
  * Include example `docker-compose.yml` for deployment. Help maintain this along with Dockerfile as we go.

---

## VIII. Maintenance

* Additionally, try to stay on top of these:
  * **Refactor** non‑atomic code into feature folders.
  * **Migrate** mock‑heavy tests to integration tests—or document why mocks remain.
  * Keep both `Dockerfile` (release runtime) and `Dockerfile.devcontainer` (dev/test runtime) updated with all latest dependencies.
