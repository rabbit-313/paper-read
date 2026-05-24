# Paper Read

GitHub Pages archive for Japanese paper translations and Ochiai-format summary slides.

## Contents

- `index.html`: paper archive UI
- `papers/<paper-id>/translation/`: translated paper HTML and Markdown
- `papers/<paper-id>/slides/`: HTML slide deck and slide source
- `recommendations/latest.json`: daily paper recommendation data for the homepage
- `tools/daily_recommend.py`: collects recommender-system paper candidates
- `tools/paper_generation_watcher.py`: watches GitHub Issues and runs local Codex generation

## Current Papers

- arXiv:2503.02767 - Undertrained Image Reconstruction for Realistic Degradation in Blind Image Super-Resolution
- arXiv:1511.06939 - Session-based Recommendations with Recurrent Neural Networks

## Daily Recommendations

GitHub Actions runs `tools/daily_recommend.py` every morning in Japan time and commits
`recommendations/latest.json` plus a dated Markdown digest. The homepage reads that JSON
and shows candidate papers with short summaries and a request button.

Run it manually:

```sh
python3 tools/daily_recommend.py
```

## Local Codex Generation Queue

The homepage request button opens a prefilled GitHub Issue with the `paper-generate`
label. Keep a local watcher running on this Mac to process those issues with Codex skills:

```sh
python3 tools/paper_generation_watcher.py --poll
```

For a dry run that only prints the Codex prompt:

```sh
python3 tools/paper_generation_watcher.py --dry-run
```

Prerequisites:

- `gh auth login -h github.com`
- a clean git working tree before the watcher starts
- the local `codex` CLI available on `PATH`

The watcher asks Codex to use `translate-paper-pdf` and `paper-ochiai-slides`, verifies
that `index.html` files were generated, commits the result, pushes it, comments on the
Issue, and closes the Issue.
