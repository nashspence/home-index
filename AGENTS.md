## 1. Testing
- **CI only**: All tests run in GitHub Actions on every push to any branch.  
- **No local test runs**, at all. Don't do it! They will nearly always fail because you cannot run them in the correct environment. If you want to see test results, ask me to create a PR of the current code, CI will run, and I will relate any failures back to you.

## 2. Feature Requirements
**Each feature must**:
  1. `<FeatureName>` will be in title case and intuitive.
  2. Be atomic—deliver one standalone piece of functionality.
  3. Separate feature specific code into directories named `<FeatureName>`. Keep shared code out of these directories.
  4. Have an integration test (no unit-only tests). Avoid mocks, stubs, dummies, etc. unless absolutely necessary, and special note in code comments if and why not possible in some case.  

## 3. Documentation
In `README.md`: 

1. Section: **Who**: An expansive deeply logical keyphrase-heavy description of who would benefit from using this and why.
2. Section: **Features**:
  ```md
  [**<FeatureName>**](<path/to/testfile>#Lstart-Lend) — <short description of how the person described in **Purpose** >
  ````
  * `<FeatureName>` should feel like an search engine keyphrase, what a person would search for
  * **Test name must match the `<FeatureName>` as closely as possible.**
  * Link points directly to the test file and line range.
3. Section: **Contributions**:
  Indicates that PRs are welcome and describes how to use the dev container, CI, etc. Similar to AGENTS.md but for actual people.


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
* **Environment**: Use the same `Dockerfile` + `docker-compose` setup for both testing and release as much as possible. Do not shy away from downloading and installing **anything** necessary to run or test as part of the Dockerfile - not matter how big or complex. It should be a complete *real* environment.
* **Workflows**:

  * **`.github/workflows/test.yml`**

    * Trigger on **push** any branch.
    * One step per feature test; each step named `<FeatureName>`.
  * **`.github/workflows/release.yml`**

    * Trigger on **GitHub release** events (tag or release).
    * **Docker images**:

      * Build & push to registry following org naming/tag conventions.
      * In the release notes, include the full image reference (e.g. `ghcr.io/org/repo:tag`).

## 6. Development Container

* **Base image**: `cruizba/ubuntu-dind:latest` (Docker-in-Docker).
* **`.devcontainer/`** must contain:

  * `Dockerfile.devcontainer` (FROM `cruizba/ubuntu-dind:latest`)
  * `devcontainer.json` (references `docker-compose.yml` & `postStart.sh`)
  * `docker-compose.yml` (defines dev services)
  * `postStart.sh` (initialization script)
* Launch via VS Code Remote – Containers; all services run inside DinD, mirroring CI/release setup.
* Document any VS Code settings or extensions in `devcontainer.json`.

## 7. Convention

Aside from above, search for and strive to follow modern strict conventions for the langauge and environment wherever possible. Maintain a `check.sh` script that runs known common linters and a popular formatter with default settings - run before each push fix any issues they output BEFORE you push.

```
