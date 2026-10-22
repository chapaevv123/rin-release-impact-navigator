# Static replay demo: deployment preparation

RIN's public demo can be served as static HTML, CSS, JavaScript and saved JSON. It makes **no live NVIDIA, Zetaris or Meterless request**. Do not publish it until the owner approves a public repository and deployment.

## Build the exact static output

From the repository root, with Python 3.11+:

```sh
python bench/build_static_demo.py
python -m http.server 8001 --bind 127.0.0.1 --directory public_demo
```

Open `http://127.0.0.1:8001/` or `/ui/`. The root page redirects relatively to `./ui/`, so it also works under a GitHub Pages project subpath. The build script verifies both evidence bundles and checks the saved sponsor receipt relationship before copying an explicit allowlist into `public_demo/`. `public_demo/manifest.json` records hashes, sizes and the `SAVED_REPLAY_ONLY` mode. The output includes 13 files: the root page, five UI files, five evidence JSON files, Cursor provenance Markdown and the manifest. It contains no server, runtime package, key, Docker configuration or paid API dependency.

Do not serve the whole source repository as the hosted site. The UI's relative `../artifacts/` and `../docs/` paths are preserved in the allowlisted output. Hash routing (`#/home`, `#/investigation`, `#/releases`, `#/evidence`, `#/hypotheses`, `#/replays`) needs no server rewrite.

## Vercel, after explicit publication approval

The checked-in `vercel.json` sets `buildCommand` to `python3 bench/build_static_demo.py` and `outputDirectory` to `public_demo`. Vercel's [build settings](https://vercel.com/docs/builds/configure-a-build) support a custom build command and output directory; only output files are served. Use the repository root as the project root and the **Other** framework preset. No environment variables are required. Connecting a Git repository or using the Vercel CLI can create a deployment, so both remain approval-gated. Vercel cloud execution has **not** been tested; the local static output and browser behavior have been tested.

Alternatively, after approval, publish only the `public_demo/` contents through a dedicated GitHub Pages source or a manually triggered Pages workflow. [GitHub Pages publishing-source documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) describes the branch and Actions options. This repository intentionally contains no push-triggered deployment workflow.

## Local acceptance checklist

- Verify `/` redirects to `/ui/`, all five UI assets and five JSON receipts load, and the Cursor document link resolves.
- Visit every route; use Back/Forward and switch cases without losing the route.
- Select all five causal nodes, Graph/Timeline, Zoom/Fit, hypothesis records and sponsor receipts.
- Download the selected evidence JSON. Confirm `REVIEW` for the real case and safe `UNKNOWN` when a required bundle is unavailable.
- Check 1920×1080 and 390px, console errors and horizontal overflow.
- Audit `public_demo/manifest.json` and the final archive for credentials and unlisted files before any deployment.

No hosted URL exists yet. The README will gain one only after a real deployment is approved and checked in a public browser.
