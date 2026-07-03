# CLAUDE.md — TADA server conventions

## Code style

- **Preserve existing comments** when rewriting or extending a file. Inline
  comments explain non-obvious constraints and history that would otherwise be
  lost. Restore them verbatim; only remove a comment if the code it described
  is also being deleted.
- **Prefer `pathlib.Path` over `os.path`** for filesystem paths in new or
  rewritten code (e.g. `Path(__file__).parent / '..' / 'objects.json'` instead
  of `os.path.join(os.path.dirname(__file__), '..', 'objects.json')`). Don't
  churn untouched files just to convert existing `os.path` usage.
