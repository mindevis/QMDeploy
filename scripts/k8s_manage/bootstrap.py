"""
QMDeploy: bootstrap K3s (optional), Helm 3 (optional), затем по умолчанию Argo CD + Application «qm» (GitOps).

Точка входа: **scripts/k8s-manage.py** (подкоманда **bootstrap** или без подкоманды).

На целевом сервере, где ставится K3s, поддерживается работа только от пользователя root (установка K3s/Helm,
симлинк kubectl, kubeconfig /etc/rancher/k3s/k3s.yaml).

Режим по умолчанию: без прямого «helm upgrade qm» на хосте — стек ставит Argo CD из helm/argocd, регистрирует
Application на чарт qm-project из Git (values-argocd.yaml). Мониторинг Grafana/Prometheus в чарте по умолчанию
выключен (monitoring.enabled: false в values-argocd.yaml); включите в Git или UI Argo, когда понадобится.

Legacy: --direct-helm — прежний helm upgrade --install qm; все оставшиеся аргументы передаются в helm.

Greenfield (чистый сервер): одна команда — K3s, Helm, при необходимости секреты qm-mysql/qm-app
(**--cloud-license-key-file** или **--cloud-license-key**), **ghcr-credentials** из **`/root/.ghcr-credentials`**
(одна строка = PAT, user по умолчанию **mindevis**; см. **--ghcr-username**), затем Argo CD + Application **qm**.

Требуется: Python 3, curl; для GitOps-режима после установки K3s — доступ к API (KUBECONFIG).

Переменные окружения: NAMESPACE (по умолчанию qm), RELEASE_NAME (по умолчанию qm),
KUBECONFIG (после K3s по умолчанию /etc/rancher/k3s/k3s.yaml), INSTALL_K3S_VERSION (опционально),
SKIP_SECRET_CHECK=1, ARGOCD_HOST (алиас для --argocd-host при необходимости в обёртках).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "helm" / "qm-project"
K8S_MANAGE = ROOT / "scripts" / "k8s-manage.py"


def _has_cluster_cli() -> bool:
    return bool(shutil.which("kubectl") or shutil.which("k3s"))


def _install_k3s() -> None:
    print("Installing K3s …", flush=True)
    env = os.environ.copy()
    subprocess.run(
        "curl -sfL https://get.k3s.io | sh -",
        shell=True,
        check=True,
        env=env,
    )


def _ensure_kubectl_in_path() -> None:
    """После установки K3s в PATH должен быть kubectl (часто симлинк на k3s)."""
    if shutil.which("kubectl"):
        return
    k3s = shutil.which("k3s")
    if not k3s:
        print("ERROR: neither kubectl nor k3s in PATH after K3s install.", file=sys.stderr)
        sys.exit(1)
    dest = Path("/usr/local/bin/kubectl")
    if dest.exists() or dest.is_symlink():
        print(
            "ERROR: kubectl not in PATH but /usr/local/bin/kubectl exists; extend PATH "
            '(e.g. export PATH="/usr/local/bin:$PATH") or run as root.',
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        dest.symlink_to(k3s)
        print(f"Linked {dest} -> {k3s}", flush=True)
    except OSError as e:
        print(
            f"ERROR: kubectl missing and could not symlink {dest} ({e}). "
            "Run as root or use `k3s kubectl` with KUBECONFIG.",
            file=sys.stderr,
        )
        sys.exit(1)


def _install_helm() -> None:
    print("Installing Helm 3 (get-helm-3) …", flush=True)
    subprocess.run(
        "curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash",
        shell=True,
        check=True,
    )


def _maybe_greenfield_secrets(args: argparse.Namespace) -> None:
    """Создаёт qm-mysql / qm-app через k8s-manage secrets, если передан ключ."""
    if args.cloud_license_key_file is None and args.cloud_license_key is None:
        return

    from k8s_manage.secrets import main as secrets_main

    forward: list[str] = ["-n", args.qm_namespace]
    if args.cloud_license_key_file is not None:
        forward.extend(["--cloud-license-key-file", str(args.cloud_license_key_file)])
    else:
        forward.extend(["--cloud-license-key", args.cloud_license_key])
    if args.cloud_license_ips:
        forward.extend(["--cloud-license-ips", args.cloud_license_ips])
    if args.cloud_license_machine_ids:
        forward.extend(["--cloud-license-machine-ids", args.cloud_license_machine_ids])
    if args.cloud_license_node_names:
        forward.extend(["--cloud-license-node-names", args.cloud_license_node_names])
    if args.recreate_secrets:
        forward.append("--force")
    if args.no_scrub_history:
        forward.append("--no-scrub-history")
    if args.dry_run:
        forward.append("--dry-run")
    print("Greenfield: qm-mysql + qm-app (secrets) …", flush=True)
    secrets_main(forward)


def _maybe_ghcr_credentials(args: argparse.Namespace) -> None:
    from k8s_manage.ghcr_credentials import maybe_apply_ghcr_from_file

    user_default = (os.environ.get("GHCR_USERNAME") or "").strip() or args.ghcr_username
    maybe_apply_ghcr_from_file(
        namespace=args.qm_namespace,
        cred_path=args.ghcr_credentials_file,
        default_username=user_default,
        skip=args.skip_ghcr_credentials,
        force=args.recreate_ghcr_credentials,
        dry_run=args.dry_run,
    )


def _warn_missing_secrets(namespace: str) -> None:
    """Подсказка: без qm-mysql поды упадут до создания секретов."""
    if os.environ.get("SKIP_SECRET_CHECK"):
        return
    if not shutil.which("kubectl"):
        return
    r = subprocess.run(
        ["kubectl", "get", "secret", "qm-mysql", "-n", namespace],
        capture_output=True,
    )
    if r.returncode != 0:
        helper = K8S_MANAGE
        print(
            f"WARNING: secret qm-mysql not in namespace {namespace!r}. "
            f"Create secrets first, e.g.: python3 {helper} secrets -n {namespace} --cloud-license-key-file …\n"
            f"(suppress: SKIP_SECRET_CHECK=1)",
            file=sys.stderr,
        )


def _run_gitops_bootstrap(ns: argparse.Namespace) -> None:
    from k8s_manage.addons import main as addons_main

    forward: list[str] = [
        "--argocd",
        "--argocd-host",
        ns.argocd_host,
        "--qm-repo-url",
        ns.qm_repo_url,
        "--qm-repo-revision",
        ns.qm_repo_revision,
        "--qm-namespace",
        ns.qm_namespace,
    ]
    if ns.argocd_chart_version:
        forward.extend(["--argocd-chart-version", ns.argocd_chart_version])
    if ns.argocd_skip_qm_app:
        forward.append("--argocd-skip-qm-app")
    kc = os.environ.get("KUBECONFIG")
    if kc:
        forward.extend(["--kubeconfig", kc])
    if ns.dry_run:
        forward.append("--dry-run")
    print("GitOps: Argo CD + Application qm …", flush=True)
    addons_main(forward)
    print(
        "OK: Argo CD installed; Application «qm» syncs from Git (values-argocd.yaml). "
        "Grafana/Prometheus: set monitoring.enabled: true in values (or Argo UI), then sync — off by default.",
        flush=True,
    )


def _direct_helm_upgrade(namespace: str, release: str, helm_extra: list[str], dry_run: bool = False) -> None:
    _warn_missing_secrets(namespace)
    cmd = [
        "helm",
        "upgrade",
        "--install",
        release,
        str(CHART),
        "--namespace",
        namespace,
        "--create-namespace",
        *helm_extra,
    ]
    if dry_run:
        cmd.append("--dry-run")
    subprocess.run(cmd, check=True)
    msg = f"OK: helm release {release} (namespace {namespace})"
    if dry_run:
        msg += " (helm --dry-run)"
    print(msg, flush=True)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=(
            "Install K3s (if needed), Helm 3 (if needed), then Argo CD + GitOps Application qm by default."
        )
    )
    p.add_argument(
        "--direct-helm",
        action="store_true",
        help="Legacy: helm upgrade --install qm from local chart; pass extra helm flags after this option",
    )
    p.add_argument(
        "--skip-argocd",
        action="store_true",
        help="Stop after K3s + Helm (no Argo CD); for advanced/manual flows",
    )
    p.add_argument(
        "--argocd-host",
        default=os.environ.get("ARGOCD_HOST", "k3s.qx-dev.ru"),
        help="Argo CD Ingress FQDN (global.domain)",
    )
    p.add_argument("--argocd-chart-version", default=None, help="Pin argo-cd Helm chart version")
    p.add_argument(
        "--argocd-skip-qm-app",
        action="store_true",
        help="Install only Argo CD, do not apply Application q kubectl apply",
    )
    p.add_argument(
        "--qm-repo-url",
        default="https://github.com/mindevis/QMDeploy.git",
        help="Git repo URL for Application qm",
    )
    p.add_argument(
        "--qm-repo-revision",
        default="main",
        help="Git branch/tag for Application qm (targetRevision)",
    )
    p.add_argument(
        "--qm-namespace",
        default=os.environ.get("NAMESPACE", "qm"),
        help="Namespace where qm chart is deployed",
    )
    lic = p.add_mutually_exclusive_group()
    lic.add_argument(
        "--cloud-license-key",
        default=None,
        metavar="KEY",
        help="QMServer Cloud license — создать qm-mysql/qm-app перед Argo (как k8s-manage secrets)",
    )
    lic.add_argument(
        "--cloud-license-key-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="Файл с лицензией (предпочтительно на чистом сервере)",
    )
    p.add_argument(
        "--cloud-license-ips",
        default="",
        metavar="IPS",
        help="Опционально: привязка лицензии, IP через запятую",
    )
    p.add_argument(
        "--cloud-license-machine-ids",
        default="",
        metavar="IDS",
        help="Опционально: machine-id через запятую",
    )
    p.add_argument(
        "--cloud-license-node-names",
        default="",
        metavar="NAMES",
        help="Опционально: имена нод Kubernetes через запятую",
    )
    p.add_argument(
        "--recreate-secrets",
        action="store_true",
        help="Пересоздать Secrets (как k8s-manage secrets --force)",
    )
    p.add_argument(
        "--no-scrub-history",
        action="store_true",
        help="Не чистить history при --cloud-license-key (см. k8s-manage secrets)",
    )
    p.add_argument(
        "--ghcr-credentials-file",
        type=Path,
        default=Path("/root/.ghcr-credentials"),
        metavar="PATH",
        help="Файл: одна строка = PAT для ghcr.io (user по умолчанию mindevis), две строки: username и PAT",
    )
    p.add_argument(
        "--ghcr-username",
        default="mindevis",
        metavar="USER",
        help="Docker username для ghcr.io при однострочном PAT-файле (переопределяется GHCR_USERNAME)",
    )
    p.add_argument(
        "--skip-ghcr-credentials",
        action="store_true",
        help="Не создавать Secret ghcr-credentials из файла",
    )
    p.add_argument(
        "--recreate-ghcr-credentials",
        action="store_true",
        help="Удалить существующий ghcr-credentials в namespace и создать заново",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Предпросмотр без установки K3s/Helm и без изменений кластера: secrets dry-run, GHCR и Argo шаги в режиме DRY-RUN",
    )
    if argv is None:
        args, unknown = p.parse_known_args()
    else:
        args, unknown = p.parse_known_args(argv)

    if not (CHART / "Chart.yaml").is_file():
        print(f"ERROR: chart not found: {CHART / 'Chart.yaml'}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run and not args.direct_helm:
        if unknown:
            print("ERROR: unexpected arguments:", unknown, file=sys.stderr)
            sys.exit(1)
        print("DRY-RUN: preview only — K3s/Helm not installed, cluster not modified by this pass.\n", flush=True)
        _maybe_greenfield_secrets(args)
        _maybe_ghcr_credentials(args)
        if args.skip_argocd:
            print(
                "DRY-RUN: --skip-argocd — в реальном запуске дальше были бы K3s/Helm; здесь не имитируется.",
                flush=True,
            )
            return
        _run_gitops_bootstrap(args)
        return

    if args.direct_helm:
        if not shutil.which("helm"):
            _install_helm()
        if not _has_cluster_cli():
            _install_k3s()
            _ensure_kubectl_in_path()
        if "KUBECONFIG" not in os.environ:
            os.environ["KUBECONFIG"] = "/etc/rancher/k3s/k3s.yaml"
        _maybe_greenfield_secrets(args)
        _maybe_ghcr_credentials(args)
        namespace = os.environ.get("NAMESPACE", "qm")
        release = os.environ.get("RELEASE_NAME", "qm")
        _direct_helm_upgrade(namespace, release, unknown, dry_run=args.dry_run)
        return

    if unknown:
        print(
            "ERROR: unexpected arguments:",
            unknown,
            file=sys.stderr,
        )
        print(
            "Default mode uses Argo CD (no local helm release for qm). "
            "For legacy direct install (as root on K3s server): "
            "python3 scripts/k8s-manage.py bootstrap --direct-helm -f my-values.yaml",
            file=sys.stderr,
        )
        sys.exit(1)

    if not _has_cluster_cli():
        _install_k3s()
    _ensure_kubectl_in_path()

    if not shutil.which("helm"):
        _install_helm()

    if "KUBECONFIG" not in os.environ:
        os.environ["KUBECONFIG"] = "/etc/rancher/k3s/k3s.yaml"

    _maybe_greenfield_secrets(args)
    _maybe_ghcr_credentials(args)
    _warn_missing_secrets(args.qm_namespace)

    if args.skip_argocd:
        print(
            "OK: K3s and Helm ready (--skip-argocd). Install Argo CD manually, e.g. "
            f"python3 {K8S_MANAGE} addons --argocd",
            flush=True,
        )
        return

    _run_gitops_bootstrap(args)
