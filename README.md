# QMDeploy

Helm chart **`qm-project`** и **только Python-скрипты** для развёртывания **QM Project** в **K3s** (или любом Kubernetes) **через Helm** — основной и рекомендуемый путь. Отдельный репозиторий со **своими версиями**: **`VERSION`**, **`CHANGELOG.md`**, **`helm/qm-project/Chart.yaml`**.

## Требования

- **Helm 3**, доступ к кластеру (`KUBECONFIG`).
- **Python 3** для скриптов в **`scripts/`**.
- Для **нового K3s** на хосте: **`scripts/install-k3s-helm.py`** вызывает официальный установщик get.k3s.io, затем **`helm upgrade --install`**.

## Быстрый старт (клон репозитория)

```bash
git clone https://github.com/mindevis/QMDeploy.git
cd QMDeploy
chmod +x scripts/install-k3s-helm.py
sudo python3 scripts/install-k3s-helm.py -f /path/to/my-values.yaml
```

Секреты **`qm-mysql`** и **`qm-app`** чарт не создаёт — задайте их до/после установки (как в документации QM Project).

## Синхронизация с GitHub без полного клона

На сервере можно скачать чарт и скрипты в кэш (по умолчанию **`/opt/qm`** у root):

```bash
sudo python3 scripts/sync-from-github.py
sudo python3 /opt/qm/scripts/install-k3s-helm.py -f my-values.yaml
```

Переменные: **`QM_HELM_BASE_URL`**, **`QM_DEPLOY_BASE_URL`**, **`QM_HELM_CACHE`**, **`QM_DEPLOY_ROOT`**.

## Опционально: Argo CD и MinIO (S3)

```bash
python3 scripts/install-optional-addons.py --argocd --s3
```

Полное удаление (все Application в `argocd`, `helm uninstall`, удаление namespace):

```bash
python3 scripts/install-optional-addons.py --uninstall-argocd
python3 scripts/install-optional-addons.py --uninstall-s3
python3 scripts/install-optional-addons.py --uninstall-argocd --uninstall-s3
```

**Argo CD:** по умолчанию UI на **`https://k3s.qx-dev.ru`** (Ingress, класс **traefik**, как у чарта **`qm-project`**; значения — **`helm/argocd/values-k3s.yaml`**). Другой хост: **`--argocd-host example.com`**. В DNS добавьте A-запись **`k3s.qx-dev.ru`** на IP ноды (или LB).

После установки Argo CD скрипт **создаёт Application `qm`** (`kubectl apply` из шаблона **`helm/argocd/applications/qm-project.application.yaml.tpl`**): в UI сразу виден **QM Project** (чарт **`helm/qm-project`**, values **`values-argocd.yaml`** — домены **\*.qx-dev.ru**). Источник в Git: **`--qm-repo-url`** (по умолчанию публичный **`https://github.com/mindevis/QMDeploy.git`**), ревизия **`--qm-repo-revision`** (по умолчанию **`main`**). Чтобы не регистрировать приложение (только Argo CD): **`--argocd-skip-qm-app`**.

**Секреты** **`qm-mysql`** / **`qm-app`** Argo CD не создаёт — их нужно завести в namespace **`qm`** (или в том, что задан **`--qm-namespace`**) до/после первого sync. Приватный репозиторий QMDeploy: сначала добавьте репо в **Settings → Repositories** в Argo CD, затем при необходимости передайте **`--qm-repo-url`**.

Если QM уже ставили **вручную** тем же Helm-релизом **`qm`**, первый sync GitOps может конфликтовать с существующим релизом; при проблемах: **`helm uninstall qm -n qm`** и дайте Application синхронизировать чистую установку.

### GitOps: автоматический bump образов в QMDeploy (Argo CD)

После каждого успешного push образа в GHCR CI репозиториев **QMDocs**, **QMAdmin**, **QMWeb**, **QMNetwork**, **QMServer** (cloud) вызывает переиспользуемый workflow **`QMDeploy/.github/workflows/bump-qmdeploy-image.yml`**: коммит в **`helm/qm-project/values-argocd.yaml`** (поле **`images.<service>`**), чтобы Argo CD увидел изменение и обновил кластер.

1. В **каждом** репозитории приложения (или в **организации**): секрет **`QMDEPLOY_BUMP_TOKEN`** — PAT с правом **`contents: write`** на репозиторий **QMDeploy** (classic repo / fine-grained: Contents write).
2. Сначала **смёржите и опубликуйте** ветку **`main`** репозитория **QMDeploy**, в которой есть этот workflow — иначе job **`bump-qmdeploy`** упадёт с ошибкой «workflow not found».
3. При необходимости закрепите версию workflow: вместо **`@main`** в workflow приложения укажите тег **`@vX.Y.Z`** (после релиза QMDeploy).

**Если коммита в QMDeploy нет:** в Actions откройте последний run workflow сборки образа — job **`bump-qmdeploy`** не должен быть **Skipped**. Раньше он не запускался при ручном **Run workflow** (`workflow_dispatch`); сейчас условие это учитывает. Проверьте: **push в `main`** или тег **`v*`**, секрет **`QMDEPLOY_BUMP_TOKEN`** в этом репозитории, на **`main`** в QMDeploy уже лежит **`bump-qmdeploy-image.yml`**. Если в логе bump: «Нет изменений» — в **`values-argocd.yaml`** уже записан тот же **`image ref`** (повторный push того же коммита). У **GitHub Enterprise** PAT может требовать **Authorize SSO** для организации.

Образы **QMClient** / **QMLauncher** в чарт **`qm-project`** не входят — отдельного bump нет.

## Semantic-release

```bash
npm install
export GH_TOKEN=ghp_...   # GitHub Release (classic repo или fine-grained: Contents write)
npm run release:dry       # сухой прогон
npm run release           # changelog, bump VERSION + Chart.yaml, коммит, тег, push, GitHub Release
```

**`release.config.cjs`**: по умолчанию **`repositoryUrl`** — **`git@github.com:mindevis/QMDeploy.git`** (переопределение: **`SEMANTIC_RELEASE_REPOSITORY_URL`**). После релиза выполняются **`git push origin main --follow-tags`** и создание **GitHub Release** (плагин **`@semantic-release/github`**). Без **`GH_TOKEN`** / **`GITHUB_TOKEN`** шаг GitHub упадёт; для push нужен SSH-ключ к GitHub. Релиз **из каталога субмодуля внутри qm-project**: задайте **`QM_MONOREPO_ROOT`** (абсолютный путь к корню монорепозитория), чтобы после push QMDeploy выполнился второй push корня (обновить gitlink субмодулей). Подробнее — **`tools/semantic-release/README.md`** в монорепозитории QMProject.

## Версии

| Файл | Назначение |
|------|------------|
| **`VERSION`** | Semver всего бандла QMDeploy |
| **`helm/qm-project/Chart.yaml`** | `version` / `appVersion` чарта (согласовать при релизе) |

## Монорепозиторий QMProject

Корень **[mindevis/QMProject](https://github.com/mindevis/QMProject)** подключает этот репозиторий как **git submodule `QMDeploy`**. Разработка приложений — в субмодулях приложений; деплой в k8s — здесь.

## Публикация как отдельного репозитория

См. **[PUBLISH.md](./PUBLISH.md)**.
