# Static replay demo: deployment preparation

RIN's demo is served as static HTML, CSS, JavaScript and saved JSON. It makes **no live NVIDIA, Zetaris or Meterless request**. The source repository is public; deployment of this static demo still requires owner approval.

## Build the exact static output

From the repository root, with Python 3.11+:

```sh
python bench/build_static_demo.py
python -m http.server 8001 --bind 127.0.0.1 --directory public_demo
```

Open `http://127.0.0.1:8001/` or `/ui/`. The root page redirects relatively to `./ui/`, so it also works under a GitHub Pages project subpath. The build script verifies both evidence bundles and checks the saved sponsor receipt relationship before copying an explicit allowlist into `public_demo/`. `public_demo/manifest.json` records hashes, sizes and the `SAVED_REPLAY_ONLY` mode. The output includes 13 files: the root page, five UI files, five evidence JSON files, Cursor provenance Markdown and the manifest. It contains no server, runtime package, key, Docker configuration or paid API dependency.

Do not serve the whole source repository as the hosted site. The UI's relative `../artifacts/` and `../docs/` paths are preserved in the allowlisted output. Hash routing (`#/home`, `#/investigation`, `#/releases`, `#/evidence`, `#/hypotheses`, `#/replays`) needs no server rewrite.

## Vercel, after explicit publication approval

The Vercel project must use these settings:

| Setting | Value |
| --- | --- |
| Root Directory | `.` (repository root; do not use `ui`) |
| Framework Preset | `Other` |
| Build Command | `python3 bench/build_static_demo.py` |
| Output Directory | `public_demo` |
| Install Command | Empty / disabled; no install step is needed |

The root contains `vercel.json` and the allowlist build script. With `ui` as Root Directory, Vercel cannot access `../artifacts/`, `bench/build_static_demo.py` or the root `vercel.json`; the relative evidence requests would fail. The checked-in config sets the Build Command and Output Directory above. Vercel serves only the output directory. No environment variables are required. Vercel cloud execution has **not** been tested; local build and browser behavior have been tested. Changing project settings and triggering a deployment remain approval-gated. See Vercel's [build settings](https://vercel.com/docs/builds/configure-a-build).

Alternatively, after approval, publish only the `public_demo/` contents through a dedicated GitHub Pages source or a manually triggered Pages workflow. [GitHub Pages publishing-source documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) describes the branch and Actions options. This repository intentionally contains no push-triggered deployment workflow.

## Local acceptance checklist

- Verify `/` redirects to `/ui/`, all five UI assets and five JSON receipts load, and the Cursor document link resolves.
- Visit every route; use Back/Forward and switch cases without losing the route.
- Select all five causal nodes, Graph/Timeline, Zoom/Fit, hypothesis records and sponsor receipts.
- Download the selected evidence JSON. Confirm `REVIEW` for the real case and safe `UNKNOWN` when a required bundle is unavailable.
- Check 1920×1080 and 390px, console errors and horizontal overflow.
- Audit `public_demo/manifest.json` and the final archive for credentials and unlisted files before any deployment.

No hosted URL exists yet. The README will gain one only after a real deployment is approved and checked in a public browser.
