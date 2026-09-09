# Building the standalone TADA client

`tada_client.py` is a self-contained prompt_toolkit client (stdlib +
`prompt_toolkit` only, no repo imports, no bundled data). It packages
cleanly into a standalone bundle that testers can run without installing
Python.

## Local build

From this directory (`server/`), inside `.venv`:

```
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller tada-client.spec
```

Output: `dist/tada-client/` — a folder (~30 MB) holding the launcher plus a
private Python runtime. Ship the whole folder, zipped. Testers unzip and run
`tada-client` (Linux/macOS) or `tada-client.exe` (Windows) from inside it.

This is a `--onedir` build, not `--onefile`: it starts instantly (no
unpack-to-temp on every launch) and triggers far fewer Windows antivirus
false positives. The tradeoff is a folder instead of a single file.

Smoke test:

```
./dist/tada-client/tada-client --help
```

## Cross-platform builds (GitHub Actions)

PyInstaller does **not** cross-compile — a Windows `.exe` must be built on
Windows, a Linux binary on Linux, macOS on macOS. `.github/workflows/build-client.yml`
runs the build on all three via a job matrix:

- **Trigger**: manually from the Actions tab (*Run workflow*), or by pushing
  a tag matching `client-v*` (e.g. `git tag client-v1.0 && git push origin client-v1.0`).
- **Matrix**: the `build` job is defined once and GitHub fans it out into
  three parallel runs — one each on `ubuntu-latest`, `windows-latest`,
  `macos-latest`. `fail-fast: false` means one platform failing does not
  cancel the other two.
- **Each run**: checks out the repo, sets up Python 3.12, `pip install
  prompt_toolkit pyinstaller`, runs `pyinstaller tada-client.spec`,
  smoke-tests the frozen binary with `--help`, zips `dist/tada-client/`,
  and uploads it as a workflow artifact named `tada-client-<os>`.
- **Tag builds only**: the zips are also attached to a GitHub Release for
  that tag, so testers can download from the Releases page.

To grab the binaries after a manual run: open the run in the Actions tab and
download the artifacts from the summary page.
