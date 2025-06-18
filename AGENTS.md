## Important!!!

**You must NOT run the dev, release or integrated-acceptance-test containers. You must NOT `pip install -r requirements.txt` (or similar). You must NOT `pytest -q` (or similar). Rely on CI feedback from me AFTER YOU PUSH and install only whatever dependencies you need for your own quick experiments.**

## PR Workflow

### Features Section (README.md)

* Features are listed by *canonical* title. If they are not done yet, with a one-line stub description.
* Agents will map the user request to the listed feature and craft a PR to address it.
* If no approriate feature exists yet, agent will create one. Title will be truly minimal and contain a single verb phrase. A feature is something that the user will perceive as an atomic action the application can do for them.

### PR Steps (per feature)

1. Name feature if no name exists - add to README.md.
2. Write or update the complete acceptance test.
3. Link title to exact acceptance test code lines.
4. Implement or fix code under `features/<feature_name>/src/`; shared code under `shared/src/`.
5. Replace the stub description in `README.md` with full docs.
6. Update all dependencies versions to latest, fix any issues.
7. Run `agents-check.sh`, fix any issues.
8. Push. Await potential failure output from the CI relayed by user. Fix and Push. Repeat... until PR accepted.

## Acceptance Tests

### Full Integration

* Use Docker-in-Docker via `features/<feature_name>/test/docker-compose.yml` (see [Docker-in-Docker for CI](https://docs.docker.com/build/ci/)).
* Mount inputs (`.../test/input/`) and assert outputs (`.../test/output/`).

### Partial Integration

If a feature can’t be tested in the full-release image with only controlled I/O:

1. Add a note under that feature in `README.md` explaining the limitation.
2. In your `docker-compose.yml`, bind-mount `features/<feature_name>/test/entrypoint.sh` into the release service.
3. Let that entrypoint install any test-only dependencies and invoke your acceptance tests directly—bypassing the app’s normal entrypoint.

## Formatting & Dependencies

### Style & Linting

* Humans: `check.sh` in dev container. AGENTS DO NOT RUN THIS.
* Agents: RUN `agents-check.sh` BEFORE EVERY PUSH. `agents-check.sh` installs all `check.sh` dependencies and then runs `check.sh`.
* Maintain `check.sh` to enforce strict formatter/linter (PEP 8, gofmt, rustfmt, ESLint + Prettier, etc.).

### Dependencies

Pin every dependency to an exact version (latest release).

## Development Environment

### Dev Container (`.devcontainer/`)

* Base image: [`cruizba/ubuntu-dind`](https://github.com/cruizba/ubuntu-dind).
* See [VS Code Dev Containers guide](https://code.visualstudio.com/docs/devcontainers/create-dev-container) and JSON spec: [Dev Container reference](https://devcontainers.github.io/implementors/json_reference/).
* Files:
  * `Dockerfile.devcontainer`
  * `devcontainer.json`
  * `docker-compose.yml`
  * `postStart.sh` (install, build, etc.).

## Release Environment

* Root-level `Dockerfile` and `docker-compose.yml` for production (see [Dockerfile best practices](https://docs.docker.com/build/building/best-practices/)).
* Load all settings (credentials, URLs, bind-mount paths) from a top-level `.env` file.

## CI & Testing (GitHub Actions)

**Trigger** on any push.

### Steps:
   1. Build dev container:

       ```bash
       docker-compose -f .devcontainer/docker-compose.yml up --build -d
       ```

   2. Wait for `postStart.sh`.
   3. Inside dev container:

      * Run `check.sh`.
      * Build runtime container:

        ```bash
        docker build -f Dockerfile -t repo-runtime:latest .
        ```
      * Test each feature (use [GitHub Actions matrix jobs](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/running-variations-of-jobs-in-a-workflow)). Name each test step like `"Test: <Feature Name>"`:

        ```bash
        docker-compose -f features/<feature_name>/docker-compose.yml up --abort-on-container-exit
        ```

## Logging & Observability

Emit **logs sufficient to debug from CI output alone** without stepping through code.

## Maintenance

* The README.md features section is perfect.
* Ensure the CI is setup optimally.
* Reorganize code: feature-specific under `features/`; shared code under `shared/src/`.
* Remove tests with mocks/stubs/dummies in favor of integrated acceptance tests unless specifically created as unit tests to complement already fully functioning, passing integrated acceptance tests described above. 
* Remove clutter (useless files, etc) from the repo. Maintain the .gitignore to help with this.
* Keep all Dockerfiles and dependencies lean and up to date.
* Add missing unit test coverage for features if *and only if* everything else above is done.
* Add complete formal static website documentation for application if *and only if* everything else above is done.
