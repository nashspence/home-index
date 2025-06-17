# AGENTS.md

## 1. CI-Driven Testing

* **Tests run in CI only.** GitHub Actions runs the full test suite on every pull request.
* **Do not run tests locally** except for personal debugging.

## 2. Feature Requirements

* **Every feature must:**

  * Have a dedicated, integration-style test.
  * Run in real environments using `Dockerfile` + `docker-compose` for both testing and release. Strive to reuse the same configuration for both.
  * Avoid mocks and stubs unless absolutely unavoidable.
  * Be atomic: the smallest unit delivering standalone value.
* **macOS-only code** must use a GitHub Action with `runs-on: macos-latest` (no Docker).

## 3. Documentation

* In `README.md` *Features* section, list each feature as:

  ```
  [**<feature name>**](<path/to/testfile>#Lstart-Lend) — <short description>
  ```

  * Test name must exactily match the `<feature name>`.
  * Link must point directly to the test file and line range.

## 4. CI Failure Reporting

* On CI failure, the output will be:

  ```
  tests failed, see below:
  <relevant log snippet>
  ```
