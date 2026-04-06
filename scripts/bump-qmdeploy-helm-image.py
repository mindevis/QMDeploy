#!/usr/bin/env python3
"""
Обновляет helm/qm-project/values-argocd.yaml для GitOps без пина по SHA:
  imageTag: latest
  images.<service>: ""  → образ ghcr.io/<ghcrOwner>/<service>:latest (см. templates/_helpers.tpl)

Аргументы --service и --image-ref оставлены для совместимости с CI (сообщение коммита / трассировка сборки);
в YAML тег сборки не записывается — в GHCR публикуется и latest, и SHA.
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
        help="Какой сервис собрали (для логов; в YAML выставляются все images.* одинаково)",
    )
    p.add_argument(
        "--image-ref",
        default="",
        help="Референс сборки (не пишется в values; только для сообщения коммита в workflow)",
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

    data["imageTag"] = "latest"
    if not data.get("ghcrOwner"):
        data["ghcrOwner"] = "mindevis"
    if "images" not in data or data["images"] is None:
        data["images"] = {}
    for svc in sorted(VALID_SERVICES):
        data["images"][svc] = ""

    with path.open("w", encoding="utf-8") as fp:
        yaml.dump(data, fp)


if __name__ == "__main__":
    main()
