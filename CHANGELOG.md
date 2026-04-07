# [1.9.36](https://github.com/mindevis/QMDeploy/compare/v1.9.35...v1.9.36) (2026-04-07)


### Fixed

* **CI:** **`bump-qmdeploy-image.yml`** — секрет **`QMDEPLOY_BUMP_TOKEN`** необязателен; если не задан, шаг bump пропускается (**notice**), workflow вызывающего репозитория не падает после успешной сборки образа.

# [1.9.35](https://github.com/mindevis/QMDeploy/compare/v1.9.34...v1.9.35) (2026-04-07)


### Changed

* **k8s-manage.py addons (GitOps):** Grafana и phpMyAdmin — **только** через Argo Application **qm** (`kubectl replace` + helm parameters); **`--s3`** — **Application minio** в **argocd** (Bitnami chart), без **`helm upgrade`** MinIO с хоста; **`--uninstall-s3`** сначала удаляет Application **minio**; флаг **`--minio-chart-version`**.

# [1.9.34](https://github.com/mindevis/QMDeploy/compare/v1.9.33...v1.9.34) (2026-04-07)


### Added

* **k8s-manage.py addons:** **`--grafana`** (включает **`monitoring.enabled`**, генерирует **`GRAFANA_ADMIN_PASSWORD`** в **`qm-app`**, печатает URL/логин/пароль), **`--phpmyadmin`** (**`phpmyadmin.enabled`** + **`preloadAppCredentials`**, печатает URL и учётку MySQL из **`qm-mysql`**); **`--s3`** — автопароль root при отсутствии **`--minio-root-password`**, Ingress по умолчанию **`s3.qx-dev.ru`**, флаги **`--minio-internal`**, **`--minio-ingress-class`**.

# [1.9.33](https://github.com/mindevis/QMDeploy/compare/v1.9.32...v1.9.33) (2026-04-07)


### Added

* **k8s-manage.py reset-k3s:** поэтапное удаление стека (Argo / MinIO / `helm uninstall -A` / пользовательские namespace), **`k3s-killall.sh`**, **`k3s-uninstall.sh`** (или **`k3s-agent-uninstall.sh`** с **`--agent`**), удаление **`/opt/qm`**, перезагрузка **`systemctl reboot`**; флаги **`--dry-run`**, **`--no-reboot`**, **`--keep-opt-qm`**.

# [1.9.32](https://github.com/mindevis/QMDeploy/compare/v1.9.31...v1.9.32) (2026-04-07)


### Changed

* **helm / qmnetwork:** **`command: ["./qmnetwork", "--server"]`** — как у QMServer (**`WORKDIR /app`** в образе QMNetwork v1.1.21+).

# [1.9.31](https://github.com/mindevis/QMDeploy/compare/v1.9.30...v1.9.31) (2026-04-07)


### Changed

* **helm / qmnetwork:** **`command: ["/qmnetwork", "--server"]`** — единый бинарник QMNetwork v1.1.20+ (без отдельного **`authd`**).

# [1.9.30](https://github.com/mindevis/QMDeploy/compare/v1.9.29...v1.9.30) (2026-04-07)


### Added

* **helm / qmnetwork:** переменная **`QMSERVER_INTERNAL_API_URL`** (по умолчанию **`http://qmserver:<port>`**); **`qmnetwork.qmserverInternalApiUrl`** в values.

# [1.9.29](https://github.com/mindevis/QMDeploy/compare/v1.9.28...v1.9.29) (2026-04-07)


### Added

* **helm:** опциональный встроенный **Redis** (**`redis.enabled`**, Service/Deployment **`qm-redis`**) для **QMNetwork** post-verify токенов; **`qmnetwork.redisAddr`**, пароль (**`redisPassword`** / **`redisPasswordSecret`**), **`redisDb`**; init **`wait-redis`** при заданном адресе.

# [1.9.27](https://github.com/mindevis/QMDeploy/compare/v1.9.26...v1.9.27) (2026-04-07)


### Fixed

* **helm:** ConfigMap **qmnetwork** — **`QMNETWORK_SMTP_TLS_SERVER_NAME`** (по умолчанию **`smtpRelay.hostname`** при **`smtp-relay`**) для STARTTLS к Postfix с сертификатом на публичный FQDN, не на имя Service.
* **values:** **`qmserver.config.qmnetworkSmtpTlsServerName`** (опционально).

# [1.9.26](https://github.com/mindevis/QMDeploy/compare/v1.9.25...v1.9.26) (2026-04-07)


### Fixed

* **helm:** **`qm.smtpRelayPasswordPlain`** — вместо **`regexFindSubmatch`** (нет в старых Helm из Argo CD) используются **`regexMatch`** и **`regexReplaceAll`** для разбора **`user:password`**.

# [1.9.25](https://github.com/mindevis/QMDeploy/compare/v1.9.24...v1.9.25) (2026-04-07)


### Fixed

* **helm:** при **`smtpRelay.enabled`** QMNetwork получает **`QMNETWORK_SMTP_HOST=smtp-relay`**, **USER/FROM** по **`smtpRelay.relayUserEmail`**, пароль — из **`smtp-relay-auth`** (**`QMNETWORK_SMTP_PASSWORD`** + разбор legacy **`SMTP_RELAY_USERS`**); больше не требуется дублировать пароль в **`qm-app`** для верификации email.

# [1.9.24](https://github.com/mindevis/QMDeploy/compare/v1.9.23...v1.9.24) (2026-04-07)


### Changed

* **GitOps:** **`imageRevisions`** — **QMServer** **f851018** (**v1.5.1**, **`POST /admin/users`**), **QMAdmin** **402198b** (**v1.4.1**, создание пользователя в UI).

# [1.9.23](https://github.com/mindevis/QMDeploy/compare/v1.9.22...v1.9.23) (2026-04-07)


### Removed

* **helm:** **`qmnetwork.adminEmails`** и ключ **`QMNETWORK_ADMIN_EMAILS`** из ConfigMap **qmnetwork** — админов Cloud назначайте через консоль QMServer (**`user edit`**, **`user set-primary`**).

# [1.9.22](https://github.com/mindevis/QMDeploy/compare/v1.9.21...v1.9.22) (2026-04-07)


### Changed

* **GitOps:** **`imageRevisions.qmnetwork`** → **1.1.8** (QMNetwork: исправление миграции **`004_registration_policy`**).

# [1.9.21](https://github.com/mindevis/QMDeploy/compare/v1.9.20...v1.9.21) (2026-04-07)


### Changed

* **helm:** **`ingress.hosts.phpmyadmin`** по умолчанию **`pma.qx-dev.ru`** (как в **values-argocd**).

# [1.9.20](https://github.com/mindevis/QMDeploy/compare/v1.9.19...v1.9.20) (2026-04-07)


### Features

* **helm:** опциональный **phpMyAdmin** (**`phpmyadmin.enabled`**, по умолчанию **false**) — Service **`mysql`**, Ingress при **`ingress.hosts.phpmyadmin`**; **`preloadAppCredentials`** для пользователя из **qm-mysql**.

# [1.9.19](https://github.com/mindevis/QMDeploy/compare/v1.9.18...v1.9.19) (2026-04-07)


### Changed

* **helm (mysql):** **`innodb_log_file_size`** заменён на **`innodb_redo_log_capacity`** (128 MiB) — убирает предупреждение **MY-013907** в MySQL/Percona 8.0.30+.

# [1.9.18](https://github.com/mindevis/QMDeploy/compare/v1.9.17...v1.9.18) (2026-04-07)


### Bug Fixes

* **helm (mysql):** монтирование **`mysql.cnf`** в **`/etc/my.cnf.d/z-qm.cnf`** (Percona читает **`/etc/my.cnf.d`**, а не **`/etc/mysql/conf.d`** как образ `mysql:8`). Раньше весь drop-in из ConfigMap не подключался — не действовали **`mysqlx=0`** и прочие опции **`[mysqld]`**.

# [1.9.17](https://github.com/mindevis/QMDeploy/compare/v1.9.16...v1.9.17) (2026-04-07)


### Bug Fixes

* **helm (mysql):** в **`mysql.cnf`** задано **`mysqlx=0`** — отключён MySQL X Plugin, чтобы не падать с **MY-011300** / **MY-010259** (конфликт **`mysqlx.sock`** в datadir в контейнере Percona 8.0). Классический доступ по **:3306** без изменений.

# [1.9.16](https://github.com/mindevis/QMDeploy/compare/v1.9.15...v1.9.16) (2026-04-07)


### Features

* **scripts:** после установки Argo CD (**`addons --argocd`** / **`bootstrap`**) в консоль выводятся **URL** UI, **логин `admin`** и **начальный пароль** (Secret **`argocd-initial-admin-secret`**); поддержка **`k3s kubectl`**, если **`kubectl`** не в PATH.

# [1.9.15](https://github.com/mindevis/QMDeploy/compare/v1.9.14...v1.9.15) (2026-04-07)


### Features

* **scripts:** **`--qmnetwork-database`** on **secrets** and **bootstrap** — имя БД в **`QMNETWORK_MYSQL_DSN`** (default **qmnetwork**).
* **helm:** **`mysql.qmnetworkDatabase`** — имя БД в init **`100-qmnetwork.sql`** (согласуйте с **`--qmnetwork-database`**).

# [1.9.14](https://github.com/mindevis/QMDeploy/compare/v1.9.13...v1.9.14) (2026-04-07)


### Features

* **scripts:** bootstrap accepts **`--mysql-user`** and **`--mysql-database`** (forwarded to greenfield **secrets**).

# [1.9.13](https://github.com/mindevis/QMDeploy/compare/v1.9.12...v1.9.13) (2026-04-07)


### Bug Fixes

* **scripts:** bootstrap **`--dry-run`** — предпросмотр без установки K3s/Helm и без изменений кластера; пробрасывается в secrets, GHCR и Argo addons; **`bootstrap --direct-helm`** добавляет **`helm --dry-run`**.

# [1.9.12](https://github.com/mindevis/QMDeploy/compare/v1.9.11...v1.9.12) (2026-04-07)


### Features

* **scripts:** bootstrap creates **`ghcr-credentials`** from **`/root/.ghcr-credentials`**: one line = PAT (Docker user **`mindevis`** by default / **`GHCR_USERNAME`** / **`--ghcr-username`**), two lines = username + PAT; flags **`--skip-ghcr-credentials`**, **`--recreate-ghcr-credentials`**, **`--ghcr-credentials-file`**.

### Documentation

* **readme:** greenfield file layout for GHCR PAT.

# [1.9.11](https://github.com/mindevis/QMDeploy/compare/v1.9.10...v1.9.11) (2026-04-07)


### Refactor

* **scripts:** remove standalone **`install-k3s-helm.py`**, **`create-greenfield-secrets.py`**, **`install-optional-addons.py`**; logic lives in **`scripts/k8s_manage/`**; **`k8s-manage.py`** remains the only entry.
* **scripts:** **`sync-from-github.py`** downloads the **`k8s_manage`** package files.

# [1.9.10](https://github.com/mindevis/QMDeploy/compare/v1.9.9...v1.9.10) (2026-04-07)


### Features

* **scripts:** **`k8s-manage.py`** — unified entry (no subcommand → bootstrap; **`bootstrap`**, **`secrets`**, **`addons`** delegate to existing scripts; **`--version`**).
* **scripts:** greenfield secret step in **`install-k3s-helm.py`** runs **`k8s-manage.py secrets …`** (same flags).

### Documentation

* **readme / QMDocs / sync-from-github:** prefer **`k8s-manage.py`** as primary command.

# [1.9.9](https://github.com/mindevis/QMDeploy/compare/v1.9.8...v1.9.9) (2026-04-07)


### Features

* **scripts:** `install-k3s-helm.py` — optional **`--cloud-license-key` / `--cloud-license-key-file`** (+ binding flags, **`--recreate-secrets`**, **`--no-scrub-history`**) runs **`create-greenfield-secrets.py`** after K3s+Helm and before Argo — single command on a clean server.

### Documentation

* **readme / QMDocs:** simplify greenfield to one **`install-k3s-helm.py`** flow; **`--skip-argocd`** only for advanced use.

# [1.9.8](https://github.com/mindevis/QMDeploy/compare/v1.9.7...v1.9.8) (2026-04-07)


### Bug Fixes

* **scripts:** `create-greenfield-secrets.py` — use **`k3s kubectl`** when **`kubectl` is missing; default **`KUBECONFIG`** to **`/etc/rancher/k3s/k3s.yaml`**; clear error if cluster not installed (run **`install-k3s-helm.py --skip-argocd`** first).

### Documentation

* **readme:** greenfield order — **--skip-argocd** before secrets on empty server.

# [1.9.7](https://github.com/mindevis/QMDeploy/compare/v1.9.6...v1.9.7) (2026-04-07)


### Features

* **scripts:** `create-greenfield-secrets.py` — **`--cloud-license-key-file`**; after **`--cloud-license-key`** scrubs matching line from shell history files (`HISTFILE`, `~/.bash_history`, `~/.zsh_history`); **`--no-scrub-history`** / **`QM_NO_SCRUB_HISTORY`**.

### Documentation

* **readme / QMDocs:** recommend license file; **history -d -1** for in-memory bash history.

# [1.9.6](https://github.com/mindevis/QMDeploy/compare/v1.9.5...v1.9.6) (2026-04-07)


### Features

* **scripts:** `create-greenfield-secrets.py` — license/bindings **only via CLI** (`--cloud-license-key`, etc.); **`--dry-run`** prints a masked preview without cluster changes.

### Documentation

* **readme / QMDocs:** examples without `export`; document `--dry-run`.

# [1.9.5](https://github.com/mindevis/QMDeploy/compare/v1.9.4...v1.9.5) (2026-04-07)


### Features

* **scripts:** `create-greenfield-secrets.py` — required **QMServer Cloud** license (`--cloud-license-key` / `QMSERVER_CLOUD_LICENSE_KEY`), optional binding env flags; auto-generates **QMSecret** keys in `qm-app` for GitOps defaults.

### Documentation

* **readme:** Greenfield Cloud checklist (license, **ghcr-credentials**, **QMSERVER_CLOUD_K8S**).

# [1.9.4](https://github.com/mindevis/QMDeploy/compare/v1.9.3...v1.9.4) (2026-04-07)


### Documentation

* **readme/scripts:** K3s deploy server — operations documented as **root-only**; examples use `python3` without `sudo`.

# [1.9.3](https://github.com/mindevis/QMDeploy/compare/v1.9.2...v1.9.3) (2026-04-07)


### Features

* **scripts:** `install-k3s-helm.py` greenfield by default — optional K3s, auto Helm 3 (get-helm-3), then Argo CD + Application `qm` via `install-optional-addons.py`; legacy direct install behind `--direct-helm`.
* **helm:** `values-argocd.yaml` — explicit `monitoring.enabled: false` (Grafana/Prometheus off until enabled in Git or Argo).

### Documentation

* **readme:** GitOps-first flow, Grafana off by default, MinIO still optional via `install-optional-addons.py`.

# [1.9.2](https://github.com/mindevis/QMDeploy/compare/v1.9.1...v1.9.2) (2026-04-07)


### Bug Fixes

* **ci:** bump workflow — fetch/reset main and re-run YAML bump before each push (with retries) to avoid merge conflicts when several services update `values-argocd.yaml` at once.

# [1.9.1](https://github.com/mindevis/QMDeploy/compare/v1.9.0...v1.9.1) (2026-04-07)


### Features

* **helm:** initContainer `wait-mysql` for QMNetwork (same as QMServer) to avoid migrate races on first boot.
* **scripts:** `create-greenfield-secrets.py` for minimal `qm-mysql` + `qm-app` on empty cluster; `install-k3s-helm.py` warns if `qm-mysql` is missing.

### Documentation

* **readme:** greenfield / full reinstall steps (secrets, `helm uninstall`, delete PVC).

# [1.9.0](https://github.com/mindevis/QMDeploy/compare/v1.8.0...v1.9.0) (2026-04-06)


### Features

* **helm:** imageRevisions for Argo rollout on :latest ([faf8f75](https://github.com/mindevis/QMDeploy/commit/faf8f75f4d2d5479e44f55a949f5557edd4c01e6))

# [1.8.1](https://github.com/mindevis/QMDeploy/compare/v1.8.0...v1.8.1) (2026-04-06)


### Features

* **helm:** `imageRevisions.<service>` + аннотация pod — Argo CD выкатывает новый digest при `:latest`; bump-скрипт пишет тег из `--image-ref`.

# [1.8.0](https://github.com/mindevis/QMDeploy/compare/v1.7.0...v1.8.0) (2026-04-06)


### Features

* **helm:** auto Secret smtp-relay-auth for Postfix (noreply + generated password) ([0e8b574](https://github.com/mindevis/QMDeploy/commit/0e8b5742782a55983d40ca788d4c5d271e433a5f))

# [1.7.0](https://github.com/mindevis/QMDeploy/compare/v1.6.0...v1.7.0) (2026-04-06)


### Features

* **gitops:** bump script sets imageTag latest, no SHA pins in values-argocd ([ec166d0](https://github.com/mindevis/QMDeploy/commit/ec166d00b709543ec27b6ac06279132f131ef902))

# [1.6.0](https://github.com/mindevis/QMDeploy/compare/v1.5.0...v1.6.0) (2026-04-06)


### Features

* **argocd:** enable qmsecret and smtp-relay in values-argocd ([6e31d1d](https://github.com/mindevis/QMDeploy/commit/6e31d1d129381d8aec657eddc80ce20209102c0e))

# [1.5.0](https://github.com/mindevis/QMDeploy/compare/v1.4.2...v1.5.0) (2026-04-06)


### Bug Fixes

* **helm:** QMNETWORK_OAUTH_REDIRECT_URIS for qmserver PKCE ([783af89](https://github.com/mindevis/QMDeploy/commit/783af8932d99ff4a8395c80f60bebfb00de4dcdf))


### Features

* **helm:** qmnetwork.port 9087, sync Service/Ingress/QMServer ([80858ea](https://github.com/mindevis/QMDeploy/commit/80858ea844ff8ba514867dab9da6b9449c2690cb))
* **helm:** qmsecret.port 9088, sync Service/Ingress/QMServer config ([8120b25](https://github.com/mindevis/QMDeploy/commit/8120b25faac371a19320e682ee3ddab45052c429))
* **helm:** QMSERVER_SUPER_ADMIN_EMAILS for primary admin ([59c81e0](https://github.com/mindevis/QMDeploy/commit/59c81e0abd529c3113998eadc066ff1f6d279b78))

## [1.4.7](https://github.com/mindevis/QMDeploy/compare/v1.4.6...v1.4.7) (2026-04-06)


### Changed

* **GitOps:** `values-argocd.yaml` — образ **`qmsecret`**; README: явный список сервисов для **`bump-qmdeploy-helm-image.py`** (включая **`qmsecret`**).

## [1.4.6](https://github.com/mindevis/QMDeploy/compare/v1.4.5...v1.4.6) (2026-04-06)


### Changed

* **helm `qmnetwork`:** порт по умолчанию **9087** (`qmnetwork.port`), **`QMNETWORK_INTERNAL_URL`**, Service и Ingress согласованы; QMServer остаётся на **8080**.

## [1.4.5](https://github.com/mindevis/QMDeploy/compare/v1.4.4...v1.4.5) (2026-04-06)


### Changed

* **helm `qmsecret`:** порт по умолчанию **9088** (`qmsecret.port`), **`QMSECRET_BASE_URL`** и Service/Ingress согласованы; не **8080** (QMServer/QMNetwork).

## [1.4.4](https://github.com/mindevis/QMDeploy/compare/v1.4.3...v1.4.4) (2026-04-03)


### Features

* **helm:** опциональный **QMSecret** (`qmsecret.enabled`), мониторинг **Grafana/Prometheus** (`monitoring.enabled`, Ingress **`monit.qx-dev.ru`**), согласование **`VERSION`** с **`Chart.yaml`**.

## [1.4.2](https://github.com/mindevis/QMDeploy/compare/v1.4.1...v1.4.2) (2026-04-06)


### Bug Fixes

* **ci:** rebase QMDeploy main before git push in bump workflow ([a4daca1](https://github.com/mindevis/QMDeploy/commit/a4daca13f6a9272bfb12b992610ab9f72fc74626))

## [1.4.2](https://github.com/mindevis/QMDeploy/compare/v1.4.1...v1.4.2) (2026-04-03)


### Changed

* **Helm `values.yaml`**: по умолчанию **`ingress.hosts.auth`** = **`auth.qx-dev.ru`** (QMNetwork); переопределение только для своего домена.

## [1.4.1](https://github.com/mindevis/QMDeploy/compare/v1.4.0...v1.4.1) (2026-04-06)


### Bug Fixes

* **release:** add semantic-release --no-ci for real local push ([8fd9ef7](https://github.com/mindevis/QMDeploy/commit/8fd9ef71de33d667fdbdbb13b3b884603f7c04c8))

# [1.4.0](https://github.com/mindevis/QMDeploy/compare/v1.3.0...v1.4.0) (2026-04-06)


### Features

* **gitops:** reusable workflow and script to bump images in values-argocd ([b419d09](https://github.com/mindevis/QMDeploy/commit/b419d095e77d72c9e68fc11085bb76080f295187))
* **script:** uninstall Argo CD and MinIO S3 (--uninstall-argocd, --uninstall-s3) ([818b17a](https://github.com/mindevis/QMDeploy/commit/818b17a93f1083be99c4fd5be5e4eeef45dd30bb))

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

### Changed

- **GitOps**: job **`bump-qmdeploy`** в workflow сборки образов также запускается при **`workflow_dispatch`** (раньше только при **`push`** в `main` / тег `v*`), чтобы ручной **Run workflow** обновлял **`values-argocd.yaml`** в QMDeploy.

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
