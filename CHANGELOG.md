# [1.3.0](https://github.com/mindevis/QMDeploy/compare/v1.2.0...v1.3.0) (2026-04-06)


### Features

* **release:** push to origin and create GitHub Release after semantic-release ([c54b209](https://github.com/mindevis/QMDeploy/commit/c54b209b1cbfeb3966ad9a03d5284babd86a1f4c))

# Changelog

All notable changes to **QMDeploy** (Helm chart and K3s install scripts for QM Project) are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

- **`VERSION`** — semver of the whole deploy bundle (scripts + chart alignment).
- **`helm/qm-project/Chart.yaml`** — `version` and `appVersion` track the chart; keep in sync with **`VERSION`** on release.

## [Unreleased]

### Added

- **GitOps CI**: переиспользуемый workflow **`.github/workflows/bump-qmdeploy-image.yml`**, скрипт **`scripts/bump-qmdeploy-helm-image.py`** и блок **`images`** в **`helm/qm-project/values-argocd.yaml`** — CI приложений коммитит новый ref образа в QMDeploy для Argo CD (секрет **`QMDEPLOY_BUMP_TOKEN`** в репозиториях приложений).
- **`scripts/install-optional-addons.py`**: флаги **`--uninstall-argocd`** и **`--uninstall-s3`** — полное удаление Argo CD (Application → Helm → namespace `argocd`) и MinIO (Helm → namespace из **`--minio-namespace`**).

## [1.2.0] - 2026-04-06

### Added

- **Argo CD Application `qm`**: после **`--argocd`** скрипт создаёт приложение GitOps на чарт **`qm-project`** (шаблон **`helm/argocd/applications/qm-project.application.yaml.tpl`**, values **`helm/qm-project/values-argocd.yaml`**). Флаги: **`--argocd-skip-qm-app`**, **`--qm-repo-url`**, **`--qm-repo-revision`**, **`--qm-namespace`**.

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
