# QMDeploy

Helm chart **`qm-project`** и **только Python-скрипты** для развёртывания **QM Project** в **K3s** (или любом Kubernetes) **через Helm** — основной и рекомендуемый путь. Отдельный репозиторий со **своими версиями**: **`VERSION`**, **`CHANGELOG.md`**, **`helm/qm-project/Chart.yaml`**.

**Сервер K3s:** все шаги от **root**; основной вход — **`scripts/k8s-manage.py`** (подкоманды **bootstrap** / **secrets** / **addons**; реализация — **`scripts/k8s_manage/`**). **`sync-from-github.py`** для кэша **`/opt/qm`**.

## Требования

- **Python 3** для скриптов в **`scripts/`**; **curl** для установки K3s и Helm.
- **Режим по умолчанию (bootstrap):** **K3s**, **Helm**, секреты **`qm-mysql`/`qm-app`**, **Argo CD** + Application **qm** (GitOps **`values-argocd.yaml`**).
- **Legacy-прямой Helm:** **`python3 scripts/k8s-manage.py bootstrap --direct-helm -f my-values.yaml`**.

## Первичное развёртывание (новый сервер и пустой K3s)

1. **DNS** (если нужен Ingress): A-записи на IP ноды под хосты из **`values-argocd.yaml`** (по умолчанию **`*.qx-dev.ru`**) или ваш overlay.

2. **Файл от root** — PAT для образов GHCR:

   ```bash
   cd QMDeploy
   install -m 600 /dev/null /root/.ghcr-credentials && nano /root/.ghcr-credentials   # одна строка: PAT (read:packages); user = mindevis
   ```

   Для **другого** GitHub-пользователя: две строки в **`/root/.ghcr-credentials`** (username, затем PAT) или **`GHCR_USERNAME`** / **`--ghcr-username`** при однострочном PAT.

3. **Одна команда от root** — K3s, Helm, секреты **`qm-mysql` + `qm-app`**, **`ghcr-credentials`** из файла (если не **`--skip-ghcr-credentials`**), Argo CD и Application **qm**:

   ```bash
   python3 scripts/k8s-manage.py
   ```

   MySQL в секретах: **`--mysql-user`**, **`--mysql-database`**; пересоздать секреты: **`--recreate-secrets`**. GHCR: **`--ghcr-credentials-file`**, **`--recreate-ghcr-credentials`**, **`--skip-ghcr-credentials`**. **`--dry-run`** — только предпросмотр. Прочие флаги: **`--argocd-host`**, **`--qm-repo-url`**, **`--qm-repo-revision`**, **`--qm-namespace`**, **`--argocd-skip-qm-app`**, **`--skip-argocd`**. Переменные: **`NAMESPACE`**, **`KUBECONFIG`**, **`SKIP_SECRET_CHECK=1`**, **`ARGOCD_HOST`**, **`GHCR_USERNAME`**.

   Отдельно только секреты / **`--dry-run`**: **`python3 scripts/k8s-manage.py secrets --help`**.

4. **GHCR вручную** (если пропустили файл): создайте **`ghcr-credentials`** в **`qm`** (`kubectl create secret docker-registry …`), иначе образы не скачаются — при необходимости **Sync** в Argo ещё раз.

5. **Мониторинг (Grafana):** в **`values-argocd.yaml`** по умолчанию **`monitoring.enabled: false`**. Включение — в Git или Argo, **`GRAFANA_ADMIN_PASSWORD`** в **`qm-app`** при необходимости.

6. **phpMyAdmin (опционально):** по умолчанию **`phpmyadmin.enabled: false`**. Чтобы поднять UI к MySQL в кластере: **`phpmyadmin.enabled: true`**, задайте **`ingress.hosts.phpmyadmin`** (и A-запись в DNS), выполните **Sync**. Подключение к серверу **`mysql:3306`**; войти вручную (**root** / пароль из Secret **`qm-mysql`**) или включите **`phpmyadmin.preloadAppCredentials: true`** — тогда подставится **`MYSQL_USER`** из **`qm-mysql`** (права приложения, не суперпользователь). В продакшене ограничьте доступ.

7. **Полная переустановка** с нуля (потеря данных MySQL и загрузок): при **GitOps** сначала удалите Application **qm** в **argocd** (cascade/prune в Argo удалит ресурсы релиза **qm**). Либо вручную: `kubectl delete application qm -n argocd`, затем при «залипшем» релизе **`helm uninstall qm -n qm`**. Далее PVC и namespace:

   ```bash
   kubectl delete pvc -n qm --all
   ```

   При необходимости: `kubectl delete namespace qm`; namespace снова создаст **`k8s-manage.py secrets`**.

## Быстрый старт (клон репозитория)

```bash
git clone https://github.com/mindevis/QMDeploy.git
cd QMDeploy
# см. выше: /root/.ghcr-credentials (PAT, user по умолчанию mindevis)
python3 scripts/k8s-manage.py
```

## Синхронизация с GitHub без полного клона

На сервере можно скачать чарт и скрипты в кэш (по умолчанию **`/opt/qm`** у root):

```bash
python3 scripts/sync-from-github.py
python3 /opt/qm/scripts/k8s-manage.py
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

Полный bootstrap выполняет **`scripts/k8s-manage.py`** (по умолчанию подкоманда **bootstrap**; см. выше).

Только дополнения без переустановки K3s, или **MinIO**:

```bash
python3 scripts/k8s-manage.py addons --argocd --s3
python3 scripts/k8s-manage.py addons --grafana
python3 scripts/k8s-manage.py addons --phpmyadmin
```

**Grafana / phpMyAdmin / MinIO** выполняются **через Argo CD**, а не `helm upgrade` с сервера: для **qm** обновляется Application **qm** (helm parameters + refresh), для **MinIO** создаётся Application **minio** (чарт Bitnami с общего Helm-репозитория). Нужен уже установленный **Argo CD** и Application **qm** (`addons --argocd`). Grafana: patch Secret **`qm-app`** и параметр **`monitoring.enabled`**: MinIO: **`--minio-chart-version`** при необходимости (по умолчанию зафиксирована версия чарта). **`--uninstall-s3`**: `kubectl delete application minio -n argocd`. Учётные данные по-прежнему печатаются в консоль.

Полное удаление (все Application в `argocd`, `helm uninstall`, удаление namespace):

```bash
python3 scripts/k8s-manage.py addons --uninstall-argocd
python3 scripts/k8s-manage.py addons --uninstall-s3
python3 scripts/k8s-manage.py addons --uninstall-argocd --uninstall-s3
```

### Полный сброс ноды: кластер K3s, данные и перезагрузка

Чтобы **полностью убрать** пользовательские namespace и релизы, **деинсталлировать K3s**, удалить кэш **`/opt/qm`** (если был `sync-from-github`) и **перезагрузить сервер** без переустановки ОС:

```bash
cd QMDeploy   # или python3 /opt/qm/scripts/k8s-manage.py …
python3 scripts/k8s-manage.py reset-k3s --yes
```

Справка и опции (**`--dry-run`**, **`--no-reboot`**, **`--keep-opt-qm`**, worker: **`--agent`**):

```bash
python3 scripts/k8s-manage.py reset-k3s --help
```

**Только root.** Лицензии и **`/root/.ghcr-credentials`** скрипт **не удаляет**. После reboot снова выполните **`k8s-manage.py bootstrap`** (или полный вызов с ключом Cloud). На **worker-нодах** (агент K3s): **`reset-k3s --agent --yes`**.

**Argo CD:** по умолчанию UI на **`https://k3s.qx-dev.ru`** (Ingress, класс **traefik**, как у чарта **`qm-project`**; значения — **`helm/argocd/values-k3s.yaml`**). Другой хост: **`--argocd-host`** у **`k8s-manage.py`** / **`k8s-manage.py addons`**. В DNS добавьте A-запись **`k3s.qx-dev.ru`** на IP ноды (или LB). После установки **`bootstrap`** / **`addons --argocd`** скрипт сразу печатает **URL** (`https://<хост>/`), **логин `admin`** и **начальный пароль** из Secret **`argocd-initial-admin-secret`** (если чтение не удалось — команда **`kubectl`** для ручного декодирования).

При установке Argo CD создаётся **Application `qm`** (`kubectl apply` из шаблона **`helm/argocd/applications/qm-project.application.yaml.tpl`**): в UI виден **QM Project** (чарт **`helm/qm-project`**, values **`values-argocd.yaml`**). Источник в Git: **`--qm-repo-url`**, ревизия **`--qm-repo-revision`**. Чтобы не регистрировать приложение (только Argo CD): **`--argocd-skip-qm-app`**.

**Секреты** **`qm-mysql`** / **`qm-app`** Argo CD не создаёт — их нужно завести в namespace **`qm`** (или в том, что задан **`--qm-namespace`**) до/после первого sync. Приватный репозиторий QMDeploy: сначала добавьте репо в **Settings → Repositories** в Argo CD, затем при необходимости передайте **`--qm-repo-url`**.

Если QM уже ставили **вручную** тем же Helm-релизом **`qm`**, первый sync GitOps может конфликтовать с существующим релизом; при проблемах: **`helm uninstall qm -n qm`** и дайте Application синхронизировать чистую установку.

### GitOps: автоматический bump образов в QMDeploy (Argo CD)

После каждого успешного push образа в GHCR CI репозиториев **QMDocs**, **QMAdmin**, **QMWeb**, **QMServer** (cloud) вызывает переиспользуемый workflow **`QMDeploy/.github/workflows/bump-qmdeploy-image.yml`**: коммит в **`helm/qm-project/values-argocd.yaml`** — **`imageTag: latest`**, все **`images.<service>`** пустые, плюс **`imageRevisions.<service>`** = тег из сборки (short SHA / `latest`). Эта ревизия попадает в **аннотацию pod** (`qm-project.io/image-revision`), чтобы при том же **`image: …:latest`** Argo CD увидел изменение манифеста и выкатил новый digest. Сообщение коммита содержит референс сборки. Скрипт **`scripts/bump-qmdeploy-helm-image.py`** принимает **`--service`** и **`--image-ref`**.

1. В **каждом** репозитории приложения (или в **организации**): секрет **`QMDEPLOY_BUMP_TOKEN`** — PAT с правом **`contents: write`** на репозиторий **QMDeploy** (classic repo / fine-grained: Contents write).
2. Сначала **смёржите и опубликуйте** ветку **`main`** репозитория **QMDeploy**, в которой есть этот workflow — иначе job **`bump-qmdeploy`** упадёт с ошибкой «workflow not found».
3. При необходимости закрепите версию workflow: вместо **`@main`** в workflow приложения укажите тег **`@vX.Y.Z`** (после релиза QMDeploy).

**Без секрета **`QMDEPLOY_BUMP_TOKEN`**:** job **`bump-qmdeploy`** завершается **успешно** (GitHub **notice**), общий workflow остаётся зелёным — пуш образа в GHCR не блокируется; автокоммит в QMDeploy просто не выполняется.

**Если коммита в QMDeploy нет:** в Actions откройте последний run workflow сборки образа. Проверьте: **push в `main`** или тег **`v*`**, при необходимости секрет **`QMDEPLOY_BUMP_TOKEN`**, на **`main`** в QMDeploy уже лежит **`bump-qmdeploy-image.yml`**. Если в логе bump: «Нет изменений» — **`values-argocd.yaml`** уже в нужном состоянии. **Красный крест** чаще из‑за падающего **build-and-push** (Docker/npm/go), из‑за **истёкшего PAT** при `git push` в QMDeploy или из‑за ошибки «workflow not found» (ветка **`main`** в QMDeploy без этого workflow). У **GitHub Enterprise** PAT может требовать **Authorize SSO** для организации.

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
