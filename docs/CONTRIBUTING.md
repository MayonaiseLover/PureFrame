# Contributing to PureFrame

First off, thank you for considering contributing to PureFrame! We're building a tool that helps families enjoy media together, and your help makes that possible.

## Quick Start
1. Fork the repo.
2. Run `pip install -e ".[dev]"`
3. Install the Tauri prerequisites if you're touching the GUI: `cd gui && npm install`.
4. Make your changes in a new branch.
5. Submit a PR!

## Core Architecture
- **Pipeline (`pureframe/pipeline/`)**: Core processing loop. Treat detection, planning, and applying as distinct, decoupled phases.
- **Tauri GUI (`gui/`)**: A stateless front-end that uses the Python CLI under the hood. Avoid putting heavy Python logic into the Rust layer.

## Pull Request Process
1. Ensure your code passes all linting (`flake8`) and type-checking (`mypy --strict`).
2. Update the README or `docs/` with details of changes to the interface.
3. Tests run automatically via GitHub Actions, but try to run `pytest` locally first.

## Community
Join our Discord server to discuss architecture changes before writing huge PRs. The invite link is in the README.
