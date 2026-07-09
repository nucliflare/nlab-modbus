# Releasing

## Version scheme

This project uses [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.
While the API is still settling, breaking changes may land as `MINOR` bumps
(the `0.x` convention) — this doc will call out the point where `1.0.0` locks
the public API.

## Single source of truth

The version string lives in exactly one place:

```
src/nlab_modbus/_version.py   ->   __version__ = "0.1.0"
```

Everything else derives from it, nothing else stores its own copy:

- `pyproject.toml` reads it dynamically (`tool.setuptools.dynamic`), so the
  built package and `pip show` report the same number.
- `scripts/build_nuitka.py` imports it directly to stamp the Windows `.exe`
  version resource.
- The git tag that triggers a release (`vX.Y.Z`) is expected to match it
  exactly. `scripts/check_release_tag.py` runs as the first CI step on both
  Gitea and GitHub and **fails the build** if the pushed tag and
  `__version__` disagree — this is what prevents drift between the file and
  the tag across two independently-pushed remotes.

## Bumping the version

Use [bump-my-version](https://github.com/callowayproject/bump-my-version)
(installed via the `dev` extra) instead of editing the file and tagging by
hand — it does both atomically so they can't drift apart:

```bash
bump-my-version bump patch   # 0.1.0 -> 0.1.1
bump-my-version bump minor   # 0.1.0 -> 0.2.0
bump-my-version bump major   # 0.1.0 -> 1.0.0
```

This edits `src/nlab_modbus/_version.py`, commits (`chore: bump version
... -> ...`), and creates an annotated tag `vX.Y.Z` on that commit. Nothing
is pushed yet — that's a separate, deliberate step (see below).

## Release flow across two remotes

`origin` (Gitea) is internal and updated often; `github` is public and
updated rarely. Tag once, decide separately when each remote actually builds
it:

1. Bump the version and tag locally:
   ```bash
   bump-my-version bump minor
   ```
2. Push to Gitea first — this is your internal build/QA pass:
   ```bash
   git push origin main --follow-tags
   ```
   `--follow-tags` pushes only the annotated tag(s) reachable from `main`
   that the remote doesn't have yet — i.e. exactly the `vX.Y.Z` tag you just
   created, and nothing else. Prefer this over `--tags`, which pushes
   *every* local tag unconditionally, including any stray/experimental ones
   you never meant to publish.

   The Gitea Actions workflow (`.gitea/workflows/build.yaml`) builds the
   Windows and Linux binaries, then a `release` job downloads both and
   publishes them as assets on the Gitea Release for tag `vX.Y.Z` (via
   `akkuman/gitea-release-action`). This stays internal to the Gitea
   instance, but gives teammates a stable, discoverable download link
   instead of digging through Actions-run artifacts (which expire).
3. Once the internal build is verified, publish the same commit + tag to
   GitHub when you're ready for a public release:
   ```bash
   git push github main --follow-tags
   ```
   The GitHub Actions workflow (`.github/workflows/build.yaml`) builds both
   platforms and then a `release` job downloads both artifacts and publishes
   a public GitHub Release for tag `vX.Y.Z`, with the binaries attached and
   release notes auto-generated from merged PRs/commits since the last tag.

Because the tag is identical on both remotes, the same commit and the same
`__version__` are what get validated internally and what eventually ships
publicly — there's no separate "internal version" vs. "public version" to
reconcile.

## One-off / hotfix builds

`workflow_dispatch` is still enabled on both workflows for manually
triggering a build without pushing a tag (e.g. to sanity-check a branch);
these runs skip the tag/version guard's push-tag context but still go
through the same build steps.