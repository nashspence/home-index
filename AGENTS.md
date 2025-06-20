## Important!!!

**You must NOT build the dev or release containers or run integrated acceptance tests. You must NOT `pip install -r requirements.txt` (or similar). You must NOT `pytest -q` (or similar). Rely on CI feedback from me AFTER YOU PUSH and install only whatever dependencies you need for your own quick experiments.**

## Features

Features are listed as user goals with their title and number in the README.md. All features will be a minimally expressed user goal. The user goals will seem consistent with eachother. All bugs should map to a feature.

Agents will map the prompt to a listed feature and craft a PR to address it. If prompt cannot be mapped to a feature, infer the missing one and craft a PR to add it. If an appropriate feature cannot be inferred, do **not** craft a PR - request prompter to clarify intent. 

Code should be be organized as follows: **all** feature-specific code under `features/`; **all** shared code under `shared/`; **all** entrypoint code in repo root.

## How to Respond to a Prompt

1. Write or update the acceptance test, if applicable.
2. Implement or fix code
3. Write or update the documentation of the feature implementation in `README.md`, if applicable.
4. Update all dependencies versions to latest, fix any issues.
5. Run `agents-check.sh`, fix any issues.
6. Push.

## Acceptance Tests

### Full Integration

* Use Docker-in-Docker (see [Docker-in-Docker for CI](https://docs.docker.com/build/ci/)).
* Bind-mount `features/<feature number>/test/input/` and `features/<feature number>/test/output/` into release container. Control input files and environment config. Acceptance test will run `features/<feature number>/test/docker-compose.yml` and assert expected output files, responses, etc. from all containers.

## Formatting & Dependencies

### Style & Linting

* Humans: `check.sh` in dev container. AGENTS DO NOT RUN THIS.
* Agents: RUN `agents-check.sh` BEFORE EVERY PUSH. `agents-check.sh` installs all `check.sh` dependencies and then runs `check.sh`.
* Maintain `check.sh` to enforce language appropriate formatter/typing/linter (ruff, mypy, Black (+ isort, autoflake), ESLint + Prettier, etc.) - strict as possible given repo state at the current PR.

### Dependencies

Pin every dependency to an exact version (latest release).

## Development Environment

### Dev Container (`.devcontainer/`)

* Base image: [`cruizba/ubuntu-dind`](https://github.com/cruizba/ubuntu-dind).
* See [VS Code Dev Containers guide](https://code.visualstudio.com/docs/devcontainers/create-dev-container) and JSON spec: [Dev Container reference](https://devcontainers.github.io/implementors/json_reference/).
* Always create or update the following before push as development runtime:
  * `Dockerfile.devcontainer`
  * `devcontainer.json`
  * `docker-compose.yml`
  * `postStart.sh` (install, build, etc.).

## Release Environment

* Always create or update root-level `Dockerfile` and `docker-compose.yml` as application runtime (see [Dockerfile best practices](https://docs.docker.com/build/building/best-practices/)) before push.
* Load all settings (credentials, URLs, bind-mount paths) from a top-level `.env` file.

## CI & Testing (GitHub Actions (`.github/workflows/test.yml`))

Always create or update the file before push. It must **Trigger** on any push.

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
      * Test each feature (use [GitHub Actions matrix jobs](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/running-variations-of-jobs-in-a-workflow)). Name each test step like `"Test <feature number>: <feature name>"`:

        ```bash
        docker-compose -f features/<feature number>/test/docker-compose.yml up --abort-on-container-exit
        ```

## Logging & Observability

Emit **logs sufficient to debug from CI output alone** without stepping through code. Always create or update logging to improve CI step failure output before push.

## Incremental Adoption

* Target `mypy --strict .` etc., but if there are too many issues to fix in a single PR, conform code touched as part of the current PR and leave the rest untyped.
* Attempt to reorganize all code as specified under appropriate directories, but if there are too many issues to fix in a single PR, make note in the README.md of code that is not organized appropriately and just conform code touched as part of the current PR.

## Maintenance

If instructed to preform **maintenance**, craft a PR that incrementally progresses **one** of the following (ordered by priority):

1. Rich documentation of each feature in the README.md features section completely describes the implementation details and how it assists with that particular goal. Otherwise, keep the README.md very sparse.
2. `.github/workflows/test.yml` is perfectly clean and matches expectations.
3. Fully organized codebased - as per expectation described above.
4. Each feature is has an appropriate passing integrated acceptance test, as described above. 
5. Dockerfiles and dependencies lean and up to date.
6. Strict typing (if applicable) - `mypy --strict .` or similar.
7. Clean repo: remove all clutter (useless files, unnecessary code, etc) from the repo. (maintain the .gitignore to help with this.)
8. Full unit test coverage for features. (if *and only if* everything else above is done)
9. Formal static website documentation (`docs`) for application (if *and only if* everything else above is done)
