"""Container entrypoint: fix data-dir ownership as root, then drop to the unprivileged app user.

Existing installs have files in ./data created by the old root container (some with mode
600). Running the app as a non-root user would make them unreadable, so on every start
this script (still root) gives ownership of DATA_DIR to DPP_UID:DPP_GID, drops all
privileges and execs the real command. If the container is already started as a
non-root user (``user:`` in docker-compose), it just execs the command.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _chown_tree(root: Path, uid: int, gid: int) -> int:
    changed = 0
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    for current, dirs, files in os.walk(root):
        for name in [None, *dirs, *files]:
            path = current if name is None else os.path.join(current, name)
            try:
                st = os.lstat(path)
                if st.st_uid != uid or st.st_gid != gid:
                    os.lchown(path, uid, gid)
                    changed += 1
            except OSError as exc:
                print(f"[DPP] entrypoint: cannot chown {path}: {exc}", file=sys.stderr)
    return changed


def main(argv: list[str]) -> None:
    command = argv or ["python", "dpp_entrypoint.py"]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        uid = int(os.environ.get("DPP_UID", "10001"))
        gid = int(os.environ.get("DPP_GID", "10001"))
        if uid != 0:
            data_dir = Path(os.environ.get("DPP_DATA_DIR") or "/app/data")
            changed = _chown_tree(data_dir, uid, gid)
            if changed:
                print(f"[DPP] entrypoint: {changed} file(s) in {data_dir} now owned by {uid}:{gid}")
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
            os.environ["HOME"] = "/tmp"
    os.umask(0o077)  # new data files (db, uploads, backups, tokens) are private by default
    os.execvp(command[0], command)


if __name__ == "__main__":
    main(sys.argv[1:])
