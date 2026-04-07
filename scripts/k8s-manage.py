#!/usr/bin/env python3
"""
QMDeploy — единая точка входа для K3s / Helm / Argo CD / секретов / дополнений.

Реализация: пакет **k8s_manage/** (bootstrap, secrets, addons).

Подкоманды (можно опустить **bootstrap** — команды с флагом вида **--...** сразу идут в bootstrap):

  bootstrap   K3s, Helm, опционально greenfield-secrets, Argo + Application **qm**.
  secrets     Только **qm-mysql** / **qm-app** (**--dry-run**, ключ лицензии …).
  addons      **--argocd**, **--s3**, деинсталляции и т.д.
  reset-k3s   Полное удаление стека в кластере, деинсталляция K3s, кэша **/opt/qm**, перезагрузка ОС (**root**).

Примеры:

  python3 scripts/k8s-manage.py --cloud-license-key-file /root/.qm-cloud-license
  python3 scripts/k8s-manage.py bootstrap --help
  python3 scripts/k8s-manage.py secrets --cloud-license-key-file /root/.lic --dry-run
  python3 scripts/k8s-manage.py addons --argocd --s3
  python3 scripts/k8s-manage.py addons --grafana
  python3 scripts/k8s-manage.py addons --phpmyadmin
  python3 scripts/k8s-manage.py reset-k3s --yes
  python3 scripts/k8s-manage.py --version
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from k8s_manage.cli import main as _main


if __name__ == "__main__":
    sys.exit(_main())
