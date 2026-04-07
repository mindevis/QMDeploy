"""
Опциональная установка Argo CD и MinIO (S3) через Helm 3 — отдельно от чарта qm-project.

Требуется: kubectl, Helm 3, доступ к кластеру.

Полный greenfield: **scripts/k8s-manage.py** (bootstrap вызывает этот модуль с --argocd).
Отдельно: **k8s-manage.py addons**. На сервере K3s — от root.

Пример:

  python3 scripts/k8s-manage.py addons --argocd --s3
  python3 scripts/k8s-manage.py addons --grafana
  python3 scripts/k8s-manage.py addons --phpmyadmin
  python3 scripts/k8s-manage.py addons --s3
  python3 scripts/k8s-manage.py addons --argocd --argocd-skip-qm-app
  python3 scripts/k8s-manage.py addons --s3 --minio-root-password 'секрет'
  python3 scripts/k8s-manage.py addons --uninstall-argocd
  python3 scripts/k8s-manage.py addons --uninstall-s3
  python3 scripts/k8s-manage.py addons --uninstall-argocd --uninstall-s3
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_QMDEPLOY_ROOT = Path(__file__).resolve().parents[2]


def _deploy_semver() -> str:
    """Semver из QMDeploy/VERSION (обход вверх по каталогам). Fallback — если файла нет."""
    here = Path(__file__).resolve()
    for d in (here.parent, *here.parents):
        vf = d / "VERSION"
        if vf.is_file():
            return vf.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    return "1.2.0"


def helm_cmd(args: argparse.Namespace) -> list[str]:
    cmd = ["helm"]
    if args.kubeconfig:
        cmd.extend(["--kubeconfig", args.kubeconfig])
    return cmd


def _ensure_kubeconfig() -> None:
    if os.environ.get("KUBECONFIG"):
        return
    kc = Path("/etc/rancher/k3s/k3s.yaml")
    if kc.is_file():
        os.environ["KUBECONFIG"] = str(kc)


def _kubectl_argv0() -> list[str]:
    """['kubectl'] или ['k3s', 'kubectl'] на хосте без симлинка kubectl."""
    if shutil.which("kubectl"):
        return ["kubectl"]
    if shutil.which("k3s"):
        _ensure_kubeconfig()
        return ["k3s", "kubectl"]
    return []


def kubectl_cmd(args: argparse.Namespace) -> list[str]:
    argv0 = _kubectl_argv0()
    if not argv0:
        print("ОШИБКА: нужен kubectl или k3s (команда в PATH).", file=sys.stderr)
        sys.exit(1)
    cmd = list(argv0)
    if args.kubeconfig:
        cmd.extend(["--kubeconfig", args.kubeconfig])
    return cmd


def ensure_helm() -> None:
    if not shutil.which("helm"):
        print("ОШИБКА: нужен Helm 3 (команда helm в PATH).", file=sys.stderr)
        sys.exit(1)


def ensure_kubectl() -> None:
    if not _kubectl_argv0():
        print("ОШИБКА: нужен kubectl или k3s (команда в PATH).", file=sys.stderr)
        sys.exit(1)


def run(cmd: list[str], check: bool = True) -> None:
    subprocess.run(cmd, check=check)


def _random_password() -> str:
    return secrets.token_urlsafe(24)


def _secret_key_b64(k: list[str], namespace: str, secret: str, key: str) -> str | None:
    r = subprocess.run(
        [
            *k,
            "get",
            "secret",
            secret,
            "-n",
            namespace,
            "-o",
            f"jsonpath={{.data.{key}}}",
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0 or not (r.stdout or "").strip():
        return None
    try:
        return base64.b64decode(r.stdout.strip()).decode("utf-8")
    except (ValueError, UnicodeError):
        return None


def _patch_secret_data_key(k: list[str], namespace: str, secret: str, key: str, value: str) -> None:
    b64 = base64.b64encode(value.encode("utf-8")).decode("ascii")
    patch = json.dumps({"data": {key: b64}})
    subprocess.run(
        [*k, "patch", "secret", secret, "-n", namespace, "--type", "merge", "-p", patch],
        check=True,
    )


def _argo_app_merge_helm_params(args: argparse.Namespace, updates: dict[str, str]) -> bool:
    """True если Application qm обновлена; False если нет Argo или ошибка replace."""
    k = kubectl_cmd(args)
    r = subprocess.run(
        [*k, "get", "application", "qm", "-n", "argocd", "-o", "json"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return False
    try:
        app: dict[str, Any] = json.loads(r.stdout)
    except json.JSONDecodeError:
        return False
    spec = app.setdefault("spec", {})
    source = spec.setdefault("source", {})
    helm_block = source.setdefault("helm", {})
    params_list: list[dict[str, str]] = list(helm_block.get("parameters") or [])
    by_name: dict[str, dict[str, str]] = {}
    for p in params_list:
        name = p.get("name")
        if name:
            by_name[name] = {"name": name, "value": str(p.get("value", ""))}
    for name, value in updates.items():
        by_name[name] = {"name": name, "value": str(value)}
    helm_block["parameters"] = list(by_name.values())
    app.pop("status", None)
    md = app.get("metadata")
    if isinstance(md, dict):
        md.pop("managedFields", None)
    rr = subprocess.run(
        [*k, "replace", "-f", "-"],
        input=json.dumps(app).encode("utf-8"),
        capture_output=True,
        text=True,
    )
    if rr.returncode != 0:
        print(rr.stderr or rr.stdout or "kubectl replace failed", file=sys.stderr)
        return False
    subprocess.run(
        [
            *k,
            "annotate",
            "application",
            "qm",
            "-n",
            "argocd",
            "argocd.argoproj.io/refresh=hard",
            "--overwrite",
        ],
        check=False,
    )
    print("Argo CD: Application qm обновлена (helm parameters), запрошен refresh.", flush=True)
    return True


def _helm_qm_upgrade_sets(args: argparse.Namespace, helm_sets: list[str]) -> bool:
    h = helm_cmd(args)
    chart = _QMDEPLOY_ROOT / "helm" / "qm-project"
    if not (chart / "Chart.yaml").is_file():
        print(f"ОШИБКА: нет чарта {chart}", file=sys.stderr)
        return False
    r = subprocess.run(
        [*h, "status", "qm", "-n", args.qm_namespace],
        capture_output=True,
    )
    if r.returncode != 0:
        print(
            f"ОШИБКА: Helm-релиз qm в ns {args.qm_namespace} не найден. "
            "Установите стек или создайте Application qm в Argo CD.",
            file=sys.stderr,
        )
        return False
    cmd = [
        *h,
        "upgrade",
        "qm",
        str(chart),
        "-n",
        args.qm_namespace,
        "--reuse-values",
        *helm_sets,
    ]
    return subprocess.run(cmd).returncode == 0


def _qm_set_helm_values(args: argparse.Namespace, updates: dict[str, str]) -> bool:
    if _argo_app_merge_helm_params(args, updates):
        return True
    print("Application qm в Argo CD не найдена — helm upgrade qm --reuse-values …", flush=True)
    sets: list[str] = []
    for name, value in updates.items():
        sets.extend(["--set", f"{name}={value}"])
    return _helm_qm_upgrade_sets(args, sets)


def enable_grafana_addon(args: argparse.Namespace) -> None:
    ensure_kubectl()
    k = kubectl_cmd(args)
    chk = subprocess.run(
        [*k, "get", "secret", "qm-app", "-n", args.qm_namespace, "-o", "name"],
        capture_output=True,
    )
    if chk.returncode != 0:
        print(
            f"ОШИБКА: Secret qm-app в namespace {args.qm_namespace} не найден. "
            "Создайте секреты: k8s-manage.py secrets …",
            file=sys.stderr,
        )
        sys.exit(1)
    pwd = _random_password()
    print("Grafana: monitoring.enabled=true, пароль admin → Secret qm-app (GRAFANA_ADMIN_PASSWORD) …", flush=True)
    _patch_secret_data_key(k, args.qm_namespace, "qm-app", "GRAFANA_ADMIN_PASSWORD", pwd)
    if not _qm_set_helm_values(args, {"monitoring.enabled": "true"}):
        sys.exit(1)
    subprocess.run(
        [*k, "rollout", "restart", "deployment", "qm-grafana", "-n", args.qm_namespace],
        capture_output=True,
    )
    scheme = "https"
    host = args.grafana_host.strip()
    print("", flush=True)
    print("=== Grafana ===", flush=True)
    print(f"  URL:      {scheme}://{host}/", flush=True)
    print("  Логин:    admin", flush=True)
    print(f"  Пароль:   {pwd}", flush=True)
    print(
        "  Подсказка: DNS на этот хост; при ingress.tls.enabled=false задайте "
        "monitoring.grafana.rootUrlScheme=http в values.",
        flush=True,
    )
    print("", flush=True)


def enable_phpmyadmin_addon(args: argparse.Namespace) -> None:
    ensure_kubectl()
    k = kubectl_cmd(args)
    if not _qm_set_helm_values(
        args,
        {
            "phpmyadmin.enabled": "true",
            "phpmyadmin.preloadAppCredentials": "true",
        },
    ):
        sys.exit(1)
    user = _secret_key_b64(k, args.qm_namespace, "qm-mysql", "MYSQL_USER")
    pw = _secret_key_b64(k, args.qm_namespace, "qm-mysql", "MYSQL_PASSWORD")
    scheme = "https"
    host = args.phpmyadmin_host.strip()
    print("", flush=True)
    print("=== phpMyAdmin ===", flush=True)
    print(f"  URL:      {scheme}://{host}/", flush=True)
    if user and pw:
        print(f"  MySQL user (PMA_USER): {user}", flush=True)
        print(f"  MySQL password:      {pw}", flush=True)
    else:
        print(
            "  Не удалось прочитать qm-mysql (MYSQL_USER / MYSQL_PASSWORD); войдите вручную.",
            flush=True,
        )
    print("", flush=True)


def install_argocd(args: argparse.Namespace) -> None:
    h = helm_cmd(args)
    run([*h, "repo", "add", "argo", "https://argoproj.github.io/argo-helm"], check=False)
    run([*h, "repo", "update"])
    ver: list[str] = []
    if args.argocd_chart_version:
        ver = ["--version", args.argocd_chart_version]
    values_file = _QMDEPLOY_ROOT / "helm" / "argocd" / "values-k3s.yaml"
    if not values_file.is_file():
        print(f"ОШИБКА: нет файла Helm values: {values_file}", file=sys.stderr)
        sys.exit(1)
    print("Helm: установка Argo CD (namespace argocd) …", flush=True)
    run(
        [
            *h,
            "upgrade",
            "--install",
            "argocd",
            "argo/argo-cd",
            "-n",
            "argocd",
            "--create-namespace",
            "-f",
            str(values_file),
            "--set",
            f"global.domain={args.argocd_host}",
            "--wait",
            "--timeout",
            "15m",
            *ver,
        ]
    )
    _print_argocd_access(args)
    apply_argocd_qm_application(args)


def _fetch_argocd_initial_admin_password(args: argparse.Namespace) -> str | None:
    """Читает начальный пароль admin из Secret (появляется сразу после установки чарта)."""
    k = kubectl_cmd(args)
    for _ in range(30):
        r = subprocess.run(
            [
                *k,
                "get",
                "secret",
                "argocd-initial-admin-secret",
                "-n",
                "argocd",
                "-o",
                "jsonpath={.data.password}",
            ],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            try:
                return base64.b64decode(r.stdout.strip()).decode("utf-8")
            except (ValueError, UnicodeError):
                return None
        time.sleep(2)
    return None


def _print_argocd_access(args: argparse.Namespace) -> None:
    ensure_kubectl()
    url = f"https://{args.argocd_host}/"
    pwd = _fetch_argocd_initial_admin_password(args)
    k_join = " ".join(kubectl_cmd(args))
    print("", flush=True)
    print("=== Argo CD — вход в UI ===", flush=True)
    print(f"  URL:    {url}", flush=True)
    print("  Логин:  admin", flush=True)
    if pwd:
        print(f"  Пароль: {pwd}", flush=True)
        print(
            "  (начальный пароль из Secret argocd-initial-admin-secret; после смены — см. docs Argo CD)",
            flush=True,
        )
    else:
        print(
            "  Пароль: не удалось прочитать автоматически; команда:\n"
            f"    {k_join} -n argocd get secret argocd-initial-admin-secret "
            "-o jsonpath='{.data.password}' | base64 -d && echo",
            flush=True,
        )
    print("", flush=True)


def apply_argocd_qm_application(args: argparse.Namespace) -> None:
    """Регистрирует в Argo CD Application «qm» на чарт qm-project из Git."""
    if args.argocd_skip_qm_app:
        print("Пропуск Application qm (--argocd-skip-qm-app).", flush=True)
        return
    ensure_kubectl()
    tpl = (
        _QMDEPLOY_ROOT
        / "helm"
        / "argocd"
        / "applications"
        / "qm-project.application.yaml.tpl"
    )
    if not tpl.is_file():
        print(f"ОШИБКА: нет шаблона Application: {tpl}", file=sys.stderr)
        sys.exit(1)
    text = tpl.read_text(encoding="utf-8")
    text = text.replace("__QM_DEPLOY_REPO__", args.qm_repo_url)
    text = text.replace("__QM_GIT_REVISION__", args.qm_repo_revision)
    text = text.replace("__QM_NAMESPACE__", args.qm_namespace)
    print(
        "kubectl: Application argocd/qm (Helm qm-project из Git, синхронизация с кластером) …",
        flush=True,
    )
    subprocess.run(
        [*kubectl_cmd(args), "apply", "-f", "-"],
        input=text.encode("utf-8"),
        check=True,
    )
    print(
        f"В UI Argo CD появится приложение «qm». Секреты qm-mysql / qm-app создайте в namespace "
        f"{args.qm_namespace} (чарт их не создаёт).",
        flush=True,
    )


def uninstall_argocd(args: argparse.Namespace) -> None:
    """Удаляет все Application в argocd, Helm-релиз argocd и namespace argocd."""
    ensure_kubectl()
    ensure_helm()
    k = kubectl_cmd(args)
    h = helm_cmd(args)
    ns_check = subprocess.run(
        [*k, "get", "namespace", "argocd", "-o", "name"],
        capture_output=True,
    )
    if ns_check.returncode != 0:
        print("Argo CD: namespace argocd не найден — нечего удалять.", flush=True)
        return
    print("kubectl: удаление всех Application в namespace argocd …", flush=True)
    subprocess.run(
        [
            *k,
            "delete",
            "applications.argoproj.io",
            "--all",
            "-n",
            "argocd",
            "--wait=true",
            "--timeout=5m",
        ],
        check=False,
    )
    print("Helm: uninstall argocd …", flush=True)
    subprocess.run([*h, "uninstall", "argocd", "-n", "argocd"], check=False)
    print("kubectl: удаление namespace argocd …", flush=True)
    subprocess.run(
        [*k, "delete", "namespace", "argocd", "--wait=true", "--timeout=10m"],
        check=False,
    )
    print("Argo CD: удаление завершено.", flush=True)


def uninstall_minio(args: argparse.Namespace) -> None:
    """Helm uninstall minio и удаление namespace MinIO."""
    ensure_kubectl()
    ensure_helm()
    k = kubectl_cmd(args)
    h = helm_cmd(args)
    ns = args.minio_namespace
    ns_check = subprocess.run(
        [*k, "get", "namespace", ns, "-o", "name"],
        capture_output=True,
    )
    if ns_check.returncode != 0:
        print(f"MinIO: namespace {ns} не найден — нечего удалять.", flush=True)
        return
    print(f"Helm: uninstall minio (namespace {ns}) …", flush=True)
    subprocess.run([*h, "uninstall", "minio", "-n", ns], check=False)
    print(f"kubectl: удаление namespace {ns} …", flush=True)
    subprocess.run(
        [*k, "delete", "namespace", ns, "--wait=true", "--timeout=10m"],
        check=False,
    )
    print("MinIO: удаление завершено.", flush=True)


def _print_minio_access(args: argparse.Namespace, root_password: str) -> None:
    print("", flush=True)
    print("=== MinIO (S3 API) ===", flush=True)
    print(f"  Root user:     {args.minio_root_user}", flush=True)
    print(f"  Root password: {root_password}", flush=True)
    if getattr(args, "minio_host", "").strip():
        hst = args.minio_host.strip()
        print(f"  URL (Ingress): https://{hst}/  (S3 API; консоль MinIO — см. Service/console chart)", flush=True)
        print("  Настройте DNS A/AAAA на IP ноды (или LB). Класс Ingress: traefik (K3s по умолчанию).", flush=True)
    else:
        print(
            f"  Сервис в кластере: minio.{args.minio_namespace}.svc.cluster.local (без Ingress). "
            f"Порты: helm status minio -n {args.minio_namespace}",
            flush=True,
        )
    print("", flush=True)


def install_minio(args: argparse.Namespace) -> None:
    h = helm_cmd(args)
    run([*h, "repo", "add", "bitnami", "https://charts.bitnami.com/bitnami"], check=False)
    run([*h, "repo", "update"])
    root_pw = (args.minio_root_password or "").strip() or _random_password()
    extra: list[str] = [
        "--set",
        f"auth.rootUser={args.minio_root_user}",
        "--set",
        f"auth.rootPassword={root_pw}",
    ]
    if args.minio_host.strip():
        extra.extend(
            [
                "--set",
                "ingress.enabled=true",
                "--set",
                f"ingress.hostname={args.minio_host.strip()}",
                "--set",
                f"ingress.ingressClassName={args.minio_ingress_class}",
            ]
        )
    print(f"Helm: установка MinIO (namespace {args.minio_namespace}) …", flush=True)
    run(
        [
            *h,
            "upgrade",
            "--install",
            "minio",
            "bitnami/minio",
            "-n",
            args.minio_namespace,
            "--create-namespace",
            "--wait",
            "--timeout",
            "15m",
            *extra,
        ]
    )
    _print_minio_access(args, root_pw)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=(
            "Helm: Argo CD, MinIO (S3), опционально Grafana и phpMyAdmin (чарт qm-project). "
            "Нужен хотя бы один флаг установки или удаления."
        )
    )
    p.add_argument("--argocd", action="store_true", help="Argo CD (chart argo/argo-cd, ns argocd)")
    p.add_argument("--s3", action="store_true", help="MinIO S3 (bitnami/minio); пароль сгенерируется если не задан")
    p.add_argument(
        "--grafana",
        action="store_true",
        help="Включить Grafana (monitoring.enabled), сгенерировать GRAFANA_ADMIN_PASSWORD в Secret qm-app",
    )
    p.add_argument(
        "--phpmyadmin",
        action="store_true",
        help="Включить phpMyAdmin и preload учётки из qm-mysql; показать URL и пароль MySQL",
    )
    p.add_argument(
        "--uninstall-argocd",
        action="store_true",
        help="Полное удаление Argo CD: все Application в ns argocd, helm uninstall argocd, удаление ns argocd",
    )
    p.add_argument(
        "--uninstall-s3",
        action="store_true",
        help="Полное удаление MinIO: helm uninstall minio, удаление namespace MinIO (--minio-namespace)",
    )
    p.add_argument("--kubeconfig", help="Kubeconfig для helm/kubectl")
    p.add_argument(
        "--argocd-host",
        default="k3s.qx-dev.ru",
        help="FQDN Argo CD (global.domain, Ingress; по умолчанию k3s.qx-dev.ru)",
    )
    p.add_argument("--argocd-chart-version", help="Версия Helm-чарта argo-cd")
    p.add_argument(
        "--argocd-skip-qm-app",
        action="store_true",
        help="Не создавать Application qm в Argo CD (только установка Argo CD)",
    )
    p.add_argument(
        "--qm-repo-url",
        default="https://github.com/mindevis/QMDeploy.git",
        help="Git QMDeploy для Application qm (публичный HTTPS или зарегистрированный в Argo CD)",
    )
    p.add_argument(
        "--qm-repo-revision",
        default="main",
        help="Ветка или тег QMDeploy (Argo targetRevision)",
    )
    p.add_argument(
        "--qm-namespace",
        default="qm",
        help="Namespace релиза QM (destination Application)",
    )
    p.add_argument(
        "--grafana-host",
        default="monit.qx-dev.ru",
        metavar="FQDN",
        help="Домен для вывода URL Grafana (как ingress.hosts.grafana в values-argocd.yaml)",
    )
    p.add_argument(
        "--phpmyadmin-host",
        default="pma.qx-dev.ru",
        metavar="FQDN",
        help="Домен phpMyAdmin (ingress.hosts.phpmyadmin)",
    )
    p.add_argument("--minio-namespace", default="minio", help="Namespace для MinIO")
    p.add_argument("--minio-root-user", default="minioadmin")
    p.add_argument("--minio-root-password", help="Пароль root MinIO; если не задан — случайный")
    p.add_argument(
        "--minio-host",
        default="s3.qx-dev.ru",
        metavar="FQDN",
        help="Домен Ingress MinIO (Bitnami); пусто вместе с --minio-internal",
    )
    p.add_argument(
        "--minio-internal",
        action="store_true",
        help="Не создавать Ingress у MinIO (только Service в кластере)",
    )
    p.add_argument(
        "--minio-ingress-class",
        default="traefik",
        metavar="NAME",
        help="ingress.ingressClassName для MinIO (K3s: traefik)",
    )
    p.add_argument("--dry-run", action="store_true", help="Только описание шагов")
    p.add_argument(
        "--deploy-version",
        action="store_true",
        help="Вывести semver Kubernetes deploy bundle (VERSION) и выйти",
    )
    if argv is None:
        args = p.parse_args()
    else:
        args = p.parse_args(argv)
    if args.minio_internal:
        args.minio_host = ""
    if args.deploy_version:
        print(_deploy_semver())
        return
    if args.argocd and args.uninstall_argocd:
        print("Нельзя одновременно --argocd и --uninstall-argocd.", file=sys.stderr)
        sys.exit(1)
    if args.s3 and args.uninstall_s3:
        print("Нельзя одновременно --s3 и --uninstall-s3.", file=sys.stderr)
        sys.exit(1)
    want_install = args.argocd or args.s3 or args.grafana or args.phpmyadmin
    want_uninstall = args.uninstall_argocd or args.uninstall_s3
    if not want_install and not want_uninstall:
        print(
            "Укажите хотя бы один флаг: --argocd, --s3, --grafana, --phpmyadmin, "
            "--uninstall-argocd или --uninstall-s3",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.dry_run:
        if args.uninstall_argocd:
            print(
                "DRY-RUN: kubectl delete applications.argoproj.io --all -n argocd --wait; "
                "helm uninstall argocd -n argocd; kubectl delete namespace argocd"
            )
        if args.uninstall_s3:
            print(
                f"DRY-RUN: helm uninstall minio -n {args.minio_namespace}; "
                f"kubectl delete namespace {args.minio_namespace}"
            )
        if args.argocd:
            vf = _QMDEPLOY_ROOT / "helm" / "argocd" / "values-k3s.yaml"
            print(
                "DRY-RUN: helm upgrade --install argocd argo/argo-cd -n argocd --create-namespace "
                f"-f {vf} --set global.domain={args.argocd_host}"
            )
            if not args.argocd_skip_qm_app:
                print(
                    "DRY-RUN: kubectl apply -f -  # Application argocd/qm из "
                    "helm/argocd/applications/qm-project.application.yaml.tpl "
                    f"(repo={args.qm_repo_url}, revision={args.qm_repo_revision}, "
                    f"namespace={args.qm_namespace})"
                )
        if args.s3:
            print(
                f"DRY-RUN: helm upgrade --install minio bitnami/minio -n {args.minio_namespace} "
                f"--create-namespace (+ auth, ingress если задан --minio-host)"
            )
        if args.grafana:
            print(
                "DRY-RUN: patch Secret qm-app GRAFANA_ADMIN_PASSWORD; "
                "Application qm helm: monitoring.enabled=true или helm upgrade qm --reuse-values"
            )
        if args.phpmyadmin:
            print(
                "DRY-RUN: Application qm: phpmyadmin.enabled=true, "
                "phpmyadmin.preloadAppCredentials=true (или helm upgrade)"
            )
        sys.exit(0)
    need_helm = (
        want_install
        or args.uninstall_argocd
        or args.uninstall_s3
    )
    if need_helm:
        ensure_helm()
    if args.uninstall_argocd:
        uninstall_argocd(args)
    elif args.argocd:
        install_argocd(args)
    if args.uninstall_s3:
        uninstall_minio(args)
    elif args.s3:
        install_minio(args)
    if args.grafana:
        enable_grafana_addon(args)
    if args.phpmyadmin:
        enable_phpmyadmin_addon(args)
