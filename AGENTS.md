## 1. Testing
- **CI only**: All tests run in GitHub Actions on every PR or push.  
- **No local test runs**, except for personal debugging.

## 2. Feature Requirements
- **Each feature must**:
  1. Have an integration test (no unit-only tests).  
  2. Use the same `Dockerfile` + `docker-compose` setup for both testing and release.  
  3. Avoid mocks/stubs unless absolutely necessary.  
  4. Be atomic—deliver one standalone piece of functionality.  
  5. `<FeatureName>` will be in title case and intuitive

- **macOS-only features**:  
  Use a dedicated GitHub Action with `runs-on: macos-latest` (not Docker).

## 3. Documentation
In `README.md` → **Features**:
```md
[**<FeatureName>**](<path/to/testfile>#Lstart-Lend) — <short description>
````

* **Test name must match the `<FeatureName>` as closely as possible.**
* Link points directly to the test file and line range.

## 4. CI Failure Reporting

On any CI failure, output exactly:

```
tests failed, see below:
<relevant log snippet>
```

* **Log snippet** must include all context needed to diagnose and fix the test failure.
* Agents will be asked to resolve issues using only that snippet.

## 5. Maintenance & CI Config

* **Clean up**: Always migrate non-integrated tests (ones with lots of stubs, dummies, mocks, etc) into integration tests where possible. Make special note in code comments if and why not possible in some case. Do not migrate code with such a comment.
* **Workflows**:

  * **`.github/workflows/test.yml`**

    * Trigger on **push** any branch.
    * One step per feature test; each step named `<FeatureName>`.
  * **`.github/workflows/release.yml`**

    * Trigger on **GitHub release** events (tag or release).
    * **Docker images**:

      * Build & push to registry following org naming/tag conventions.
      * In the release notes, include the full image reference (e.g. `ghcr.io/org/repo:tag`).
    * **macOS-only artifacts**:

      * Build on `runs-on: macos-latest`.
      * Package & attach as a release artifact (e.g. `.tar.gz` or `.zip`), using standard naming.

## 6. Development Container

* **Base image**: `cruizba/ubuntu-dind:latest` (Docker-in-Docker).
* **`.devcontainer/`** must contain:

  * `Dockerfile.devcontainer` (FROM `cruizba/ubuntu-dind:latest`)
  * `devcontainer.json` (references `docker-compose.yml` & `postStart.sh`)
  * `docker-compose.yml` (defines dev services)
  * `postStart.sh` (initialization script)
* Launch via VS Code Remote – Containers; all services run inside DinD, mirroring CI/release setup.
* Document any VS Code settings or extensions in `devcontainer.json`.

```
