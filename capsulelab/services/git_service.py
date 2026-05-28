from __future__ import annotations

import subprocess
from pathlib import Path

from capsulelab.core.checks import DoctorCheck
from capsulelab.core.errors import GitError_, Severity


class GitError(GitError_):
    pass


def _run(args: list[str], cwd: str | None = None) -> str:
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as e:
        raise GitError("Git is not installed.") from e
    except subprocess.TimeoutExpired as e:
        raise GitError("Git command timed out.") from e
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"Git exited with code {result.returncode}")
    return result.stdout.strip()


def init_repo(project_path: str) -> dict:
    path = str(Path(project_path).resolve())
    _run(["git", "init"], cwd=path)
    try:
        _run(["git", "config", "user.name"], cwd=path)
    except GitError:
        _run(["git", "config", "user.name", "CapsuleLab"], cwd=path)
    try:
        _run(["git", "config", "user.email"], cwd=path)
    except GitError:
        _run(["git", "config", "user.email", "capsulelab@local"], cwd=path)
    _run(["git", "add", "-A"], cwd=path)
    if not _run(["git", "status", "--porcelain"], cwd=path).strip():
        return {"status": "initialized", "path": path, "commit": ""}
    _run(["git", "commit", "-m", "Initial commit"], cwd=path)
    commit_hash = _run(["git", "rev-parse", "--short", "HEAD"], cwd=path)
    return {"status": "initialized", "path": path, "commit": commit_hash}


def git_status(project_path: str) -> dict:
    try:
        _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=project_path)
    except GitError:
        return {"is_repo": False, "branch": "", "remote": "", "dirty_files": 0, "lfs_available": False}
    try:
        branch = _run(["git", "branch", "--show-current"], cwd=project_path)
        if not branch:
            branch = _run(["git", "rev-parse", "--short", "HEAD"], cwd=project_path)
        remotes = _run(["git", "remote", "-v"], cwd=project_path)
        dirty = _run(["git", "status", "--porcelain"], cwd=project_path)
    except GitError:
        return {"is_repo": True, "branch": "", "remote": "", "dirty_files": 0, "lfs_available": False}
    lfs_available = True
    try:
        _run(["git", "lfs", "version"], cwd=project_path)
    except GitError:
        lfs_available = False
    remote = remotes.splitlines()[0] if remotes else ""
    return {
        "is_repo": True,
        "branch": branch,
        "remote": remote,
        "dirty_files": len([line for line in dirty.splitlines() if line.strip()]),
        "lfs_available": lfs_available,
    }


def ensure_repo(project_path: str) -> None:
    try:
        _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=project_path)
    except GitError as e:
        raise GitError(f"Not a git repository: {project_path}") from e


def history(project_path: str, limit: int = 10) -> list[dict]:
    ensure_repo(project_path)
    raw = _run(
        ["git", "log", f"--max-count={limit}", "--pretty=format:%h%x09%an%x09%ad%x09%s", "--date=short"],
        cwd=project_path,
    )
    commits = []
    for line in raw.splitlines():
        parts = line.split("\t", 3)
        if len(parts) == 4:
            commits.append({"hash": parts[0], "author": parts[1], "date": parts[2], "subject": parts[3]})
    return commits


def branches(project_path: str) -> dict:
    ensure_repo(project_path)
    raw = _run(["git", "branch", "--list"], cwd=project_path)
    items = []
    current = ""
    for line in raw.splitlines():
        name = line.strip()
        active = name.startswith("* ")
        if active:
            name = name[2:]
            current = name
        items.append({"name": name, "current": active})
    return {"current": current, "branches": items}


def switch_branch(project_path: str, branch: str, create: bool = False) -> dict:
    ensure_repo(project_path)
    args = ["git", "switch"]
    if create:
        args.append("-c")
    args.append(branch)
    output = _run(args, cwd=project_path)
    return {"status": "switched", "branch": branch, "output": output}


def fetch(project_path: str, remote: str = "origin") -> dict:
    ensure_repo(project_path)
    output = _run(["git", "fetch", remote], cwd=project_path)
    return {"status": "fetched", "remote": remote, "output": output}


def pull(project_path: str, remote: str = "origin", branch: str | None = None) -> dict:
    ensure_repo(project_path)
    args = ["git", "pull", remote]
    if branch:
        args.append(branch)
    output = _run(args, cwd=project_path)
    return {"status": "pulled", "remote": remote, "branch": branch, "output": output}


def push(project_path: str, remote: str = "origin", branch: str | None = None, set_upstream: bool = False) -> dict:
    ensure_repo(project_path)
    args = ["git", "push"]
    if set_upstream:
        args.append("-u")
    args.append(remote)
    if branch:
        args.append(branch)
    output = _run(args, cwd=project_path)
    return {"status": "pushed", "remote": remote, "branch": branch, "output": output}


def commit(project_path: str, message: str, all_changes: bool = True) -> dict:
    ensure_repo(project_path)
    if all_changes:
        _run(["git", "add", "-A"], cwd=project_path)
    if not _run(["git", "status", "--porcelain"], cwd=project_path).strip():
        return {"status": "clean", "commit": "", "output": "No changes to commit"}
    output = _run(["git", "commit", "-m", message], cwd=project_path)
    commit_hash = _run(["git", "rev-parse", "--short", "HEAD"], cwd=project_path)
    return {"status": "committed", "commit": commit_hash, "output": output}


def add_remote(project_path: str, remote: str, url: str) -> dict:
    ensure_repo(project_path)
    remotes = _run(["git", "remote"], cwd=project_path).splitlines()
    if remote in remotes:
        _run(["git", "remote", "set-url", remote, url], cwd=project_path)
        return {"status": "updated", "remote": remote, "url": url}
    _run(["git", "remote", "add", remote, url], cwd=project_path)
    return {"status": "added", "remote": remote, "url": url}


def publish(project_path: str, remote_url: str, remote: str = "origin", branch: str | None = None) -> dict:
    ensure_repo(project_path)
    add_remote(project_path, remote, remote_url)
    if not branch:
        branch = _run(["git", "branch", "--show-current"], cwd=project_path) or "main"
    pushed = push(project_path, remote=remote, branch=branch, set_upstream=True)
    return {"status": "published", "remote": remote, "url": remote_url, "branch": branch, "push": pushed}


def clone(url: str, dest: str) -> str:
    _run(["git", "clone", url, dest])
    return dest


def is_git_url(source: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(source)
    return parsed.scheme in {"http", "https", "ssh", "git"} or source.startswith("git@") or source.endswith(".git")


def check_health(project_path: str) -> list[DoctorCheck]:
    try:
        git = git_status(project_path)
    except Exception:
        return [DoctorCheck(label="Git repository", severity=Severity.WARNING, ok=False, detail="Could not check")]

    if not git["is_repo"]:
        return [DoctorCheck(label="Git repository", severity=Severity.WARNING, ok=False, detail="Not a git repo")]
    checks = [
        DoctorCheck(
            label="Git: repository",
            severity=Severity.INFO,
            ok=True,
            detail=f"Branch: {git['branch'] or 'detached HEAD'}",
        ),
        DoctorCheck(
            label="Git: remote",
            severity=Severity.WARNING,
            ok=bool(git["remote"]),
            detail=git["remote"] or "No remote configured",
        ),
        DoctorCheck(
            label="Git: clean working tree",
            severity=Severity.WARNING,
            ok=not bool(git["dirty_files"]),
            detail=f"{git['dirty_files']} uncommitted file(s)" if git["dirty_files"] else "Clean",
        ),
        DoctorCheck(
            label="Git LFS",
            severity=Severity.INFO,
            ok=True,
            detail="Available" if git["lfs_available"] else "Not installed — optional for large files",
        ),
    ]
    return checks
