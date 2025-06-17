# AGENTS.md

## 1. Testing
- **CI only**: All tests run in GitHub Actions on every PR or push.  
- **No local test runs**, except for personal debugging.

## 2. Feature Requirements
- **Each feature must**:
  1. Have an integration test (no unit-only tests).  
  2. Use the same `Dockerfile` + `docker-compose` setup for both testing and release.  
  3. Avoid mocks/stubs unless absolutely necessary.  
  4. Be atomic—deliver one standalone piece of functionality.

- **macOS-only features**:  
  Use a dedicated GitHub Action with `runs-on: macos-latest` (no Docker).

## 3. Documentation
In `README.md` → **Features**:
```
[**<FeatureName>**](<path/to/testfile>#Lstart-Lend) — <short description>
```

* `<FeatureName>` will be title case and intuitive.
* Test name must match `<FeatureName>` as much as possible.
* The link must point to the test file and lines where the feature is exercised.

## 4. CI Failure Reporting

On any CI failure, output exactly:

```
tests failed, see below:
<relevant log snippet>
```

* **Log snippet must include** all context (error message, stack trace, file/line) needed to diagnose and fix the failure.
* Agents will be expected to resolve issues using only that snippet.

## 5. Maintenance & CI Config

* **Clean up**: Remove any low-value, non-integrated tests (or convert them into integration tests).
* **Workflows**:

  * **`.github/workflows/test.yml`**

    * Trigger on **push** (any branch) and **pull\_request**.
    * One step per test, named exactly `<FeatureName>`.
  * **`.github/workflows/release.yml`**

    * Trigger on **GitHub release** events (tag or release).
    * **Docker images**:

      * Build and push to Docker registry following your org’s naming/tag conventions.
      * In the GitHub release notes, include the fully-qualified image reference (e.g. `ghcr.io/org/repo:tag`).
    * **macOS-only artifacts (include only if needed)**:

      * Build (if needed) on `runs-on: macos-latest`.
      * Package and attach as a release artifact (e.g. `.tar.gz` or `.zip`), following standard GitHub naming conventions.

## 6. Development Container

* **`.devcontainer/`** must include:

  * `Dockerfile.devcontainer`
  * `devcontainer.json`
  * `docker-compose.yml` (for services used in development)
  * `postStart.sh` (setup scripts: install CLI tools, seed data, etc.)
* The devcontainer setup should mirror the CI/release Docker configuration where possible, ensuring a consistent local environment.
* Document any additional VS Code settings or extensions in `devcontainer.json`.

```
