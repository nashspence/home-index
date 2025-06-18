## PR Workflow

1. **Features Section (README.md)**

   * Features are listed by *canonical* title. If they are not done yet, with a one-line stub description.
   * Agents will map the user request to the listed feature and craft a PR to address it.
   * If no approriate feature exists yet, agent will create one. Title will be truly minimal and contain a single verb. A feature is something that the user will perceive as an atomic action the application can do for them.

2. **PR Steps (per feature)**

   1. Name feature if no name exists - add to README.md.
   2. Write or update the complete acceptance test.
   3. Link title to exact acceptance test code lines.
   4. Implement or fix code under `features/<feature_name>/src/`; shared code under `shared/src/`.
   5. Replace the stub description in `README.md` with full docs.
   6. Update all dependencies versions to latest, fix any issues.
   7. Run `agents-check.sh`, fix any issues.
   8. Push. Await feedback from the CI.

## Acceptance Tests

1. **Full Integration**

   * Use Docker-in-Docker via
     `features/<feature_name>/test/docker-compose.yml`
     (see [Docker-in-Docker for CI](https://docs.docker.com/build/ci/)).
   * Mount inputs (`.../test/input/`) and assert outputs (`.../test/output/`).

2. **Partial Integration**

   * If testing the feature on the full release with only controlled inputs and outputs is impossible, note the limitation in the README.md under that feature and bind-mount a `features/<feature_name>/test/entrypoint.sh` into the release environment using the docker-compose.yml. That entrypoint can install acceptance test specific deps and run tests bypassing the application's normal main entrypoint.

## Formatting & Dependencies

1. **Style & Linting**

   * Humans: `check.sh` in dev container.
   * Agents: `agents-check.sh` before every push. `agents-check.sh` installs all `check.sh` dependencies and then runs `check.sh`.
   * Enforce strict formatter/linter (PEP 8, gofmt, rustfmt, ESLint + Prettier, etc.).

2. **Dependencies**

   * Pin every dependency to an exact version (latest release).

## Development Environment

1. **Dev Container** (`.devcontainer/`)

   * Base image: [`cruizba/ubuntu-dind`](https://github.com/cruizba/ubuntu-dind).
   * See [VS Code Dev Containers guide](https://code.visualstudio.com/docs/devcontainers/create-dev-container) and JSON spec: [Dev Container reference](https://devcontainers.github.io/implementors/json_reference/).
   * Files:

     * `Dockerfile.devcontainer`
     * `devcontainer.json`
     * `docker-compose.yml`
     * `postStart.sh` (install, build, etc.).

2. **Usage**

   * AGENTS DO NOT USE THIS, INSTEAD RELY SOLELY ON FEEDBACK FROM THE CI RELAYED BACK AFTER PUSH. MAINTAIN THE CI METICULOUSLY.

## Release Environment

* Root-level `Dockerfile` and `docker-compose.yml` for production (see [Dockerfile best practices](https://docs.docker.com/build/building/best-practices/)).
* Load all settings (credentials, URLs, mounts) from a top-level `.env` file.

## CI & Testing (GitHub Actions)

1. **Trigger:** on any push.

2. **Steps:**
   1\.

   ```bash
   docker-compose -f .devcontainer/docker-compose.yml up --build -d
   ```

   2. Wait for `postStart.sh`.
   3. Inside container:

      * Run `check.sh`.
      * Build runtime:

        ```bash
        docker build -f Dockerfile -t repo-runtime:latest .
        ```
      * Test each feature (use [GitHub Actions matrix jobs](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/running-variations-of-jobs-in-a-workflow)). Name each test step like `"Test: <Feature Name>"`:

        ```bash
        docker-compose -f features/<feature_name>/docker-compose.yml up --abort-on-container-exit
        ```

3. **Failure Reporting:**
   * Output any Github Actions step failures exactly like:

     ```
     ci failed on <step name>, see below:
     <relevant log snippet>
     ```

## Logging & Observability

* Emit logs sufficient to debug without stepping through code.

## Maintenance

* Reorganize code: feature-specific under `features/`; shared code under `shared/src/`.
* Convert mocks/stubs into integrated acceptance tests when possible.
* Keep all Dockerfiles and dependencies lean and up to date.
* Add missing unit test coverage for features if *and only if* everything else above is done.
* Add complete formal static website documentation for application if *and only if* everything else above is done.
