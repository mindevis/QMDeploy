#!/usr/bin/env python3
"""
Обновляет images.<service> в values-argocd.yaml (Argo CD / GitOps).
Требование: pip install -r scripts/requirements-gitops.txt (ruamel.yaml).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

VALID_SERVICES = frozenset({"qmdocs", "qmadmin", "qmweb", "qmserver", "qmnetwork", "qmsecret"})


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--service",
        required=True,
        choices=sorted(VALID_SERVICES),
        help="Ключ в Values.images (имя сервиса в чарте)",
    )
    p.add_argument(
        "--image-ref",
        required=True,
        help="Полная ссылка на образ, напр. ghcr.io/org/qmdocs:1.2.3",
    )
    p.add_argument(
        "--file",
        default="helm/qm-project/values-argocd.yaml",
        help="Путь относительно корня репозитория QMDeploy",
    )
    args = p.parse_args()

    try:
        from ruamel.yaml import YAML
    except ImportError:
        print("Нужен пакет ruamel.yaml: pip install -r scripts/requirements-gitops.txt", file=sys.stderr)
        sys.exit(1)

    root = Path(__file__).resolve().parent.parent
    path = root / args.file
    if not path.is_file():
        print(f"Файл не найден: {path}", file=sys.stderr)
        sys.exit(1)

    yaml = YAML()
    yaml.preserve_quotes = True
    text = path.read_text(encoding="utf-8")
    data = yaml.load(text) or {}
    if "images" not in data or data["images"] is None:
        data["images"] = {}
    data["images"][args.service] = args.image_ref
    with path.open("w", encoding="utf-8") as fp:
        yaml.dump(data, fp)


if __name__ == "__main__":
    main()
