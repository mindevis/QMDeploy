# QMDeploy

Helm chart **`qm-project`** и **только Python-скрипты** для развёртывания **QM Project** в **K3s** (или любом Kubernetes) **через Helm** — основной и рекомендуемый путь. Отдельный репозиторий со **своими версиями**: **`VERSION`**, **`CHANGELOG.md`**, **`helm/qm-project/Chart.yaml`**.

**Сервер K3s:** все шаги установки кластера и bootstrap (**`install-k3s-helm.py`**, **`create-greenfield-secrets.py`**, **`sync-from-github.py`** в **`/opt/qm`**) выполняйте **только от пользователя root** (прямой вход или **`su -`** / **`sudo -i`**). Ниже в командах используется **`python3`** без префикса **`sudo`**.

## Требования

- **Python 3** для скриптов в **`scripts/`**; **curl** для установки K3s и Helm.
- **Режим по умолчанию:** **`scripts/install-k3s-helm.py`** при необходимости ставит **K3s** (get.k3s.io), затем **Helm 3** (официальный **get-helm-3**), затем **Argo CD** и регистрирует Application **«qm»** — стек **qm-project** выкатывается через **GitOps** (**`values-argocd.yaml`** в Git), без локального **`helm upgrade qm`** на сервере.
- **Legacy:** прямой **`helm upgrade --install`**: **`python3 scripts/install-k3s-helm.py --direct-helm -f my-values.yaml`** от root на сервере K3s (нужен готовый **Helm 3**, если не ставили через скрипт).

## Первичное развёртывание (новый сервер и пустой K3s)

1. **DNS** (если нужен Ingress): A-записи на IP ноды под ваши хосты из `values.yaml` (`ingress.hosts.*`).
2. **Секреты** в namespace **`qm`** до первого **Sync** Argo / до появления подов (иначе MySQL и приложения не стартуют):

   ```bash
   cd QMDeploy
   # от root на сервере K3s
   python3 scripts/create-greenfield-secrets.py -n qm
   ```

   Скрипт создаёт **`qm-mysql`** (`MYSQL_*`) и минимальный **`qm-app`** (`DB_DSN`, `QMNETWORK_MYSQL_DSN`, `JWT_SECRET`, `QMBILLING_ADMIN_SECRET`, `QMNETWORK_INTERNAL_SECRET`). При повторном запуске ошибка «уже существует» — используйте **`--force`** (секреты пересоздаются; смените пароли вручную, если старая БД ещё жива).

   Лицензия Cloud и прочие ключи добавьте в **`qm-app`** отдельно (`kubectl edit secret qm-app -n qm` или `kubectl create secret generic ... --dry-run=client -o yaml | kubectl apply -f -`).

3. Установка K3s (если ещё нет), Helm, **Argo CD** и автоматическая регистрация Application **qm** (синк из Git, **`values-argocd.yaml`**):

   ```bash
   chmod +x scripts/install-k3s-helm.py
   python3 scripts/install-k3s-helm.py
   ```

   Опции: **`--argocd-host`**, **`--qm-repo-url`**, **`--qm-repo-revision`**, **`--qm-namespace`**, **`--argocd-skip-qm-app`** (только Argo без Application), **`--skip-argocd`** (остановиться после K3s+Helm). Переменные: **`NAMESPACE`** (для **`--qm-namespace`** по умолчанию), **`KUBECONFIG`** (после K3s по умолчанию **`/etc/rancher/k3s/k3s.yaml`**), **`SKIP_SECRET_CHECK=1`**, **`ARGOCD_HOST`**.

   **Мониторинг (Grafana):** в **`values-argocd.yaml`** по умолчанию **`monitoring.enabled: false`** — поды не создаются. Чтобы включить: коммит/правка в Git с **`monitoring.enabled: true`** (и **`GRAFANA_ADMIN_PASSWORD`** в **`qm-app`**) или параметры в Argo CD, затем **Sync**.

4. **Полная переустановка** с нуля (потеря данных MySQL и загрузок): при **GitOps** сначала удалите Application **qm** в **argocd** (cascade/prune в Argo удалит ресурсы релиза **qm**). Либо вручную: `kubectl delete application qm -n argocd`, затем при «залипшем» релизе **`helm uninstall qm -n qm`**. Далее PVC и namespace:

   ```bash
   kubectl delete pvc -n qm --all
   ```

   При необходимости: `kubectl delete namespace qm`; namespace снова создаст **`create-greenfield-secrets.py`**.

## Быстрый старт (клон репозитория, секреты уже есть)

```bash
git clone https://github.com/mindevis/QMDeploy.git
cd QMDeploy
chmod +x scripts/install-k3s-helm.py
python3 scripts/install-k3s-helm.py
```

Если секретов ещё нет — сначала **`python3 scripts/create-greenfield-secrets.py -n qm`** (см. раздел выше).

## Синхронизация с GitHub без полного клона

На сервере можно скачать чарт и скрипты в кэш (по умолчанию **`/opt/qm`** у root):

```bash
python3 scripts/sync-from-github.py
python3 /opt/qm/scripts/install-k3s-helm.py
```

Переменные: **`QM_HELM_BASE_URL`**, **`QM_DEPLOY_BASE_URL`**, **`QM_HELM_CACHE`**, **`QM_DEPLOY_ROOT`**.

## Опционально: Grafana + Prometheus (мониторинг в кластере)

По умолчанию в пути **GitOps** (**`values-argocd.yaml`**) **`monitoring.enabled: false`**. Чтобы поднять стек, задайте **`monitoring.enabled: true`** (в Git / overlay / параметры Application). В Secret **`qm-app`** добавьте **`GRAFANA_ADMIN_PASSWORD`** (или только для отладки **`monitoring.grafana.adminPasswordPlain`** в values).

Поднимаются **Prometheus**, **Grafana** (Ingress на **`ingress.hosts.grafana`**, по умолчанию **`monit.qx-dev.ru`**), **mysqld-exporter** (учётные данные из **`qm-mysql`**) и **blackbox-exporter** (проверка HTTP **`/health`** у QMServer — метрика доступности, не внутренние метрики процесса).

Если **`ingress.tls.enabled: false`**, выставьте **`monitoring.grafana.rootUrlScheme: http`**, чтобы **`GF_SERVER_ROOT_URL`** совпадал с реальным URL.

## Опционально: мониторинг в Docker (без Kubernetes)

В корне QMDeploy:

```bash
cp .env.monitoring.example .env.monitoring
# Задайте MONITORING_MYSQL_DSN; при необходимости поправьте monitoring/docker/prometheus.yml (адрес QMServer для blackbox)
docker compose -f docker-compose.monitoring.yml --env-file .env.monitoring up -d
```

**Grafana:** `http://localhost:3030` · **Prometheus:** `http://localhost:9090`.

## Argo CD (по умолчанию) и опционально MinIO (S3)

Полный bootstrap (**K3s + Helm + Argo CD + Application qm**) выполняет **`scripts/install-k3s-helm.py`** (см. выше).

Только дополнения без переустановки K3s, или **MinIO**:

```bash
python3 scripts/install-optional-addons.py --argocd --s3
```

Полное удаление (все Application в `argocd`, `helm uninstall`, удаление namespace):

```bash
python3 scripts/install-optional-addons.py --uninstall-argocd
python3 scripts/install-optional-addons.py --uninstall-s3
python3 scripts/install-optional-addons.py --uninstall-argocd --uninstall-s3
```

**Argo CD:** по умолчанию UI на **`https://k3s.qx-dev.ru`** (Ingress, класс **traefik**, как у чарта **`qm-project`**; значения — **`helm/argocd/values-k3s.yaml`**). Другой хост: **`--argocd-host`** на **`install-k3s-helm.py`** или **`install-optional-addons.py`**. В DNS добавьте A-запись **`k3s.qx-dev.ru`** на IP ноды (или LB).

При установке Argo CD создаётся **Application `qm`** (`kubectl apply` из шаблона **`helm/argocd/applications/qm-project.application.yaml.tpl`**): в UI виден **QM Project** (чарт **`helm/qm-project`**, values **`values-argocd.yaml`**). Источник в Git: **`--qm-repo-url`**, ревизия **`--qm-repo-revision`**. Чтобы не регистрировать приложение (только Argo CD): **`--argocd-skip-qm-app`**.

**Секреты** **`qm-mysql`** / **`qm-app`** Argo CD не создаёт — их нужно завести в namespace **`qm`** (или в том, что задан **`--qm-namespace`**) до/после первого sync. Приватный репозиторий QMDeploy: сначала добавьте репо в **Settings → Repositories** в Argo CD, затем при необходимости передайте **`--qm-repo-url`**.

Если QM уже ставили **вручную** тем же Helm-релизом **`qm`**, первый sync GitOps может конфликтовать с существующим релизом; при проблемах: **`helm uninstall qm -n qm`** и дайте Application синхронизировать чистую установку.

### GitOps: автоматический bump образов в QMDeploy (Argo CD)

После каждого успешного push образа в GHCR CI репозиториев **QMDocs**, **QMAdmin**, **QMWeb**, **QMNetwork**, **QMServer** (cloud), **QMSecret** вызывает переиспользуемый workflow **`QMDeploy/.github/workflows/bump-qmdeploy-image.yml`**: коммит в **`helm/qm-project/values-argocd.yaml`** — **`imageTag: latest`**, все **`images.<service>`** пустые, плюс **`imageRevisions.<service>`** = тег из сборки (short SHA / `latest`). Эта ревизия попадает в **аннотацию pod** (`qm-project.io/image-revision`), чтобы при том же **`image: …:latest`** Argo CD увидел изменение манифеста и выкатил новый digest. Сообщение коммита содержит референс сборки. Скрипт **`scripts/bump-qmdeploy-helm-image.py`** принимает **`--service`** и **`--image-ref`**.

1. В **каждом** репозитории приложения (или в **организации**): секрет **`QMDEPLOY_BUMP_TOKEN`** — PAT с правом **`contents: write`** на репозиторий **QMDeploy** (classic repo / fine-grained: Contents write).
2. Сначала **смёржите и опубликуйте** ветку **`main`** репозитория **QMDeploy**, в которой есть этот workflow — иначе job **`bump-qmdeploy`** упадёт с ошибкой «workflow not found».
3. При необходимости закрепите версию workflow: вместо **`@main`** в workflow приложения укажите тег **`@vX.Y.Z`** (после релиза QMDeploy).

**Если коммита в QMDeploy нет:** в Actions откройте последний run workflow сборки образа — job **`bump-qmdeploy`** не должен быть **Skipped**. Раньше он не запускался при ручном **Run workflow** (`workflow_dispatch`); сейчас условие это учитывает. Проверьте: **push в `main`** или тег **`v*`**, секрет **`QMDEPLOY_BUMP_TOKEN`** в этом репозитории, на **`main`** в QMDeploy уже лежит **`bump-qmdeploy-image.yml`**. Если в логе bump: «Нет изменений» — **`values-argocd.yaml`** уже в состоянии **`imageTag: latest`** и пустых **`images.*`**. У **GitHub Enterprise** PAT может требовать **Authorize SSO** для организации.

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
