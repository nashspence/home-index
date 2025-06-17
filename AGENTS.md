## 1. Feature Requirements

**Each feature must**:

1. **`<Feature Name>`** will be in title case and intuitive.
2. Be **atomic**—deliver one standalone piece of functionality (see [Atomic Design concept](https://bradfrost.com/blog/post/atomic-web-design/)).
3. Separate feature-specific code into directories named `<Feature Name>`. Keep shared code out of these directories.
4. Have an **integration test** (no unit-only tests). Avoid [mocks, stubs, dummies, etc.](https://martinfowler.com/articles/mocksArentStubs.html) unless absolutely necessary, and add a code-comment explaining why if you must.

## 2. Testing

* **CI only**: All tests run in [GitHub Actions](https://docs.github.com/en/actions) on every push to any branch.
* **No local test runs**, at all. Don’t do it! They will nearly always fail unless you can run them in the appropriate environment (the container specified in the [Dockerfile](https://docs.docker.com/engine/reference/builder/)). If you want to see test results, ask me to create a PR of the current code, CI will run, and I will relay any failures for you to fix.

## 3. Documentation

In **`README.md`**:

1. **Who** – An expansive, deeply logical, key-phrase-heavy description of who would benefit from using this and why.
2. **Features**:

   ```md
   [**<Feature Name>**](<path/to/testfile>#Lstart-Lend) — <short description of how this helps the archetypal person described in **Who**>
   ```

   * `<Feature Name>` should feel like a search-engine key phrase—exactly what someone would type.
   * **The test name must match `<Feature Name>` as closely as possible.**
   * The link must jump directly to the relevant test lines.
3. **Contributions** – PRs are welcome. Explain how to use the dev-container, CI, etc., similar to **AGENTS.md** but written for humans. For Dev Containers reference see the [VS Code Dev Containers docs](https://code.visualstudio.com/docs/devcontainers/containers).

## 4. Logging

Use extensive **semantic/structured logging** in application code and tests, designed specifically for *logs-only* debugging. See the vendor-neutral [OpenTelemetry Logs spec](https://opentelemetry.io/docs/specs/otel/logs/) for guidance.

## 5. Maintenance & CI Config

* **Clean up** – Always migrate non-integrated tests (those heavy with stubs/mocks) into integration tests where possible. If migration is impossible, leave a clear code comment explaining why.
* **Environment** – The runtime environment is fully defined by a **Dockerfile**. Don’t hesitate to install **anything** necessary, no matter how large. It should be a complete, real runtime environment (learn more in the [Docker Best Practices guide](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)).
* **Workflows**:

  * **`.github/workflows/test.yml`** – Trigger on **push** to any branch. Build & launch the environment Dockerfile via a custom `docker-compose.ci.yml`. One step per feature test, each step named `Test: <Feature Name>`. On any test failure, output exactly:

    ```
    tests failed, see below:
    <relevant log snippet>
    ```

    `<relevant log snippet>` must include all context needed to diagnose and fix the failure.

  * **`.github/workflows/release.yml`** – Trigger on [release events](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#release-event). Include an example `docker-compose.yml`.

    * **Docker images**:

      * `username = secrets.DOCKER_USERNAME`
      * `password = secrets.DOCKER_PASSWORD`
      * Build & push to registry per org naming/tag conventions—see [ghcr authentication](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) for details.
      * Release notes must include the full image reference (e.g., `ghcr.io/nashspence/repo:tag`).

## 6. Development Container

* **Base image** – [`cruizba/ubuntu-dind:latest`](https://hub.docker.com/r/cruizba/ubuntu-dind) (Docker-in-Docker). For the DinD concept itself, see [Docker-in-Docker docs](https://docs.docker.com/build/ci/docker-in-docker/).
* **`.devcontainer/`** must contain:

  * `Dockerfile.devcontainer` (`FROM cruizba/ubuntu-dind:latest` or similar)
  * `devcontainer.json` (references `docker-compose.yml` & `postStart.sh`) – spec details in [devcontainer.json reference](https://containers.dev/implementors/json_reference).
  * `docker-compose.yml` (defines dev services) – syntax: [Compose file v3 reference](https://docs.docker.com/compose/compose-file/compose-versioning/#version-3).
  * `postStart.sh` (initialisation script)
* Launch via **VS Code Remote – Containers**; all dependencies should be pre-installed & services runnable inside DinD for a flawless, one-command dev & test experience.

## 7. Convention

Alongside everything above, search for and adopt **modern strict conventions** for the language and environment wherever possible (e.g., PEP 8, gofmt, rustfmt, ESLint + Prettier, etc.). Maintain a `check.sh` script that runs well-known linters and a popular formatter using default settings—*run it before each push* and fix issues **before** you push.
