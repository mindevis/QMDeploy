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

**Argo CD:** по умолчанию UI на **`https://k3s.qx-dev.ru`** (Ingress, класс **traefik**, как у чарта **`qm-project`**; значения — **`helm/argocd/values-k3s.yaml`**). Другой хост: **`--argocd-host example.com`**. В DNS добавьте A-запись **`k3s.qx-dev.ru`** на IP ноды (или LB).

## Semantic-release (локально)

```bash
npm install
npm run release:dry   # сухой прогон
npm run release       # changelog, bump VERSION + Chart.yaml, коммит, тег v* (push вручную)
```

**`release.config.cjs`**: по умолчанию **`repositoryUrl`** — **`https://github.com/mindevis/QMDeploy.git`**, чтобы **`git ls-remote`** не требовал SSH-ключ к **`origin`** (можно переопределить: **`SEMANTIC_RELEASE_REPOSITORY_URL`**). На GitHub должна существовать ветка **`main`**; пока репозиторий пустой и **`main`** не запушена, **`release:dry`** может завершиться с **`ERELEASEBRANCHES`** — сначала **`git push -u origin main`**. Подробнее — **`tools/semantic-release/README.md`** в монорепозитории QMProject.

## Версии

| Файл | Назначение |
|------|------------|
| **`VERSION`** | Semver всего бандла QMDeploy |
| **`helm/qm-project/Chart.yaml`** | `version` / `appVersion` чарта (согласовать при релизе) |

## Монорепозиторий QMProject

Корень **[mindevis/QMProject](https://github.com/mindevis/QMProject)** подключает этот репозиторий как **git submodule `QMDeploy`**. Разработка приложений — в субмодулях приложений; деплой в k8s — здесь.

## Публикация как отдельного репозитория

См. **[PUBLISH.md](./PUBLISH.md)**.
