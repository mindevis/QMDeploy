# Changelog

All notable changes to **QMDeploy** (Helm chart and K3s install scripts for QM Project) are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

- **`VERSION`** — semver of the whole deploy bundle (scripts + chart alignment).
- **`helm/qm-project/Chart.yaml`** — `version` and `appVersion` track the chart; keep in sync with **`VERSION`** on release.

## [Unreleased]

## [1.1.0] - 2026-04-03

### Added

- **Argo CD** (optional install): default UI host **`k3s.qx-dev.ru`**, Ingress class **traefik**, values **`helm/argocd/values-k3s.yaml`**; flag **`--argocd-host`** in **`scripts/install-optional-addons.py`**.
- **semantic-release** (local): **`package.json`** scripts **`release`** / **`release:dry`**, **`release.config.cjs`**, **`scripts/bump-qmdeploy.mjs`** for VERSION + Chart sync.

### Changed

- **`scripts/install-optional-addons.py`**: Argo CD install uses Helm values file and **`global.domain`** from **`--argocd-host`** (default **k3s.qx-dev.ru**).
- **README**: DNS and Argo CD defaults documented.

### Added (initial bundle, same release)

- Helm chart **`qm-project`**, **`scripts/install-k3s-helm.py`**, **`scripts/install-optional-addons.py`**, **`scripts/sync-from-github.py`**.
- Supported path: **K3s + Helm only** (no `kubectl apply` / migrate-from-kubectl flow).
