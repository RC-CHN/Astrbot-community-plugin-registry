"""GitHub provider implementation."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import quote, urlparse

from ...utils.git_utils import (
    GitError,
    clone_repo,
    parse_github_url,
    preflight_github_repo_size,
)
from ...utils.metadata_parser import infer_plugin_key, parse_metadata_yaml_text
from .base import GitCredential, NormalizedRepo


logger = logging.getLogger(__name__)


class GitHubProvider:
    name = "github"

    def normalize_url(self, repo_url: str, *, allowed_hosts: list[str] | None = None) -> NormalizedRepo:
        parsed = urlparse(repo_url.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(parts) < 2:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")
        owner = parts[0]
        repo = parts[1].removesuffix(".git")
        clean_repo_url = f"https://github.com/{owner}/{repo}"
        parse_github_url(clean_repo_url, allowed_hosts=allowed_hosts)

        detected_ref_type = None
        detected_ref = None
        tail = parts[2:]
        if len(tail) >= 2 and tail[0] == "tree":
            detected_ref_type = "branch"
            detected_ref = "/".join(tail[1:])
        elif len(tail) >= 2 and tail[0] == "commit":
            detected_ref_type = "commit"
            detected_ref = tail[1]
        elif len(tail) >= 3 and tail[0] == "releases" and tail[1] == "tag":
            detected_ref_type = "tag"
            detected_ref = "/".join(tail[2:])

        return NormalizedRepo(
            provider=self.name,
            repo_url=clean_repo_url,
            owner=owner,
            repo=repo,
            host="github.com",
            detected_ref_type=detected_ref_type,
            detected_ref=detected_ref,
        )

    def inspect_repo(
        self,
        repo: NormalizedRepo,
        *,
        credential: GitCredential,
        ref_type: str | None,
        ref: str | None,
        include_refs: bool,
        proxy_url: str | None,
        timeout: int | None,
    ) -> dict[str, Any]:
        repo_path = f"/repos/{quote(repo.owner)}/{quote(repo.repo)}"
        selected_ref_type = ref_type or repo.detected_ref_type or "default"

        with ThreadPoolExecutor(max_workers=3) as executor:
            repo_future = executor.submit(
                self._github_json,
                repo_path,
                credential=credential,
                proxy_url=proxy_url,
                timeout=timeout,
            )
            branches_future = (
                executor.submit(
                    self._github_json,
                    f"{repo_path}/branches?per_page=100",
                    credential=credential,
                    proxy_url=proxy_url,
                    timeout=timeout,
                )
                if include_refs
                else None
            )
            tags_future = (
                executor.submit(
                    self._github_json,
                    f"{repo_path}/tags?per_page=100",
                    credential=credential,
                    proxy_url=proxy_url,
                    timeout=timeout,
                )
                if include_refs
                else None
            )

            commit_future = None
            if selected_ref_type != "default":
                selected_ref = _selected_ref(selected_ref_type, ref, repo.detected_ref, "")
                commit_future = executor.submit(
                    self._github_json,
                    f"{repo_path}/commits/{quote(selected_ref, safe='')}",
                    credential=credential,
                    proxy_url=proxy_url,
                    timeout=timeout,
                )

            repo_payload = repo_future.result()
            branches = branches_future.result() if branches_future is not None else []
            tags = tags_future.result() if tags_future is not None else []

        default_branch = str(repo_payload.get("default_branch") or "")
        if not default_branch:
            raise GitError("GitHub repository did not include a default branch")

        branch_options = _branch_options(branches)
        tag_options = _tag_options(tags)
        selected_ref = _selected_ref(selected_ref_type, ref, repo.detected_ref, default_branch)
        commit_payload = commit_future.result() if commit_future is not None else None
        commit_info = _commit_info(commit_payload) if commit_payload is not None else None
        commit_sha = commit_info["sha"] if commit_info is not None else _commit_sha_from_refs(
            selected_ref_type,
            selected_ref,
            default_branch,
            branch_options,
            tag_options,
        )
        if not commit_sha:
            commit_payload = self._github_json(
                f"{repo_path}/commits/{quote(selected_ref, safe='')}",
                credential=credential,
                proxy_url=proxy_url,
                timeout=timeout,
            )
            commit_info = _commit_info(commit_payload)
            commit_sha = commit_info["sha"]
        if not commit_sha:
            raise GitError("GitHub commit response did not include a commit SHA")
        if commit_info is None:
            commit_info = {
                "sha": commit_sha,
                "message": None,
                "author_name": None,
                "committed_at": None,
            }
        metadata_payload = self._github_json(
            f"{repo_path}/contents/metadata.yaml?ref={quote(commit_sha, safe='')}",
            credential=credential,
            proxy_url=proxy_url,
            timeout=timeout,
        )

        return {
            "provider": self.name,
            "repo_url": repo.repo_url,
            "owner": repo.owner,
            "repo": repo.repo,
            "host": repo.host,
            "private": bool(repo_payload.get("private")),
            "default_branch": default_branch,
            "size_kb": int(repo_payload.get("size") or 0),
            "updated_at": _parse_datetime(repo_payload.get("updated_at")),
            "detected_ref_type": repo.detected_ref_type,
            "detected_ref": repo.detected_ref,
            "selected_ref_type": selected_ref_type,
            "selected_ref": selected_ref,
            "selected_commit": commit_info,
            "metadata": _metadata_preview(_decode_github_content(metadata_payload)),
            "branches": branch_options,
            "tags": tag_options,
        }

    def resolve_ref(
        self,
        repo: NormalizedRepo,
        *,
        credential: GitCredential,
        ref_type: str | None,
        ref: str | None,
        proxy_url: str | None,
        timeout: int | None,
    ) -> dict[str, Any]:
        repo_path = f"/repos/{quote(repo.owner)}/{quote(repo.repo)}"
        selected_ref_type = ref_type or repo.detected_ref_type or "default"
        if selected_ref_type == "default":
            repo_payload = self._github_json(
                repo_path,
                credential=credential,
                proxy_url=proxy_url,
                timeout=timeout,
            )
            default_branch = str(repo_payload.get("default_branch") or "")
            if not default_branch:
                raise GitError("GitHub repository did not include a default branch")
            selected_ref = default_branch
        else:
            selected_ref = _selected_ref(selected_ref_type, ref, repo.detected_ref, "")

        commit_payload = self._github_json(
            f"{repo_path}/commits/{quote(selected_ref, safe='')}",
            credential=credential,
            proxy_url=proxy_url,
            timeout=timeout,
        )
        commit_sha = str(commit_payload.get("sha") or "")
        if not commit_sha:
            raise GitError("GitHub commit response did not include a commit SHA")
        metadata_payload = self._github_json(
            f"{repo_path}/contents/metadata.yaml?ref={quote(commit_sha, safe='')}",
            credential=credential,
            proxy_url=proxy_url,
            timeout=timeout,
        )
        return {
            "selected_ref_type": selected_ref_type,
            "selected_ref": selected_ref,
            "selected_commit": _commit_info(commit_payload),
            "metadata": _metadata_preview(_decode_github_content(metadata_payload)),
        }

    def preflight_repo_size(
        self,
        repo_url: str,
        *,
        credential: GitCredential,
        max_size_kb: int,
        timeout: int | None,
        allowed_hosts: list[str] | None,
        proxy_url: str | None,
    ) -> int | None:
        return preflight_github_repo_size(
            repo_url,
            max_size_kb=max_size_kb,
            timeout=timeout,
            allowed_hosts=allowed_hosts,
            proxy_url=proxy_url,
            github_token=credential.temporary_token,
        )

    def clone_repo(
        self,
        repo_url: str,
        dest: Path,
        *,
        credential: GitCredential,
        ref: str | None,
        timeout: int | None,
        allowed_hosts: list[str] | None,
        proxy_url: str | None,
    ) -> None:
        clone_repo(
            repo_url,
            dest,
            ref=ref,
            timeout=timeout,
            allowed_hosts=allowed_hosts,
            proxy_url=proxy_url,
            github_token=credential.temporary_token,
        )

    def _github_json(
        self,
        path: str,
        *,
        credential: GitCredential,
        proxy_url: str | None,
        timeout: int | None,
    ) -> Any:
        request = urllib.request.Request(
            f"https://api.github.com{path}",
            headers=_headers(credential),
        )
        opener = _url_opener(proxy_url)
        try:
            with opener.open(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = _github_error_message(exc)
            logger.warning(
                "GitHub API request failed: path=%s status=%s message=%r rate_limit_remaining=%s rate_limit_reset=%s",
                path.split("?", 1)[0],
                exc.code,
                message,
                exc.headers.get("X-RateLimit-Remaining"),
                exc.headers.get("X-RateLimit-Reset"),
            )
            if exc.code == 404:
                raise GitError("GitHub repository, ref, or metadata.yaml was not found") from exc
            if exc.code in {401, 403}:
                raise GitError(_github_access_denied_message(exc.code, message)) from exc
            raise GitError(f"GitHub API request failed: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise GitError(f"GitHub API request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise GitError("Timed out inspecting GitHub repository") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise GitError("Failed to parse GitHub API response") from exc


def _selected_ref(
    ref_type: str,
    explicit_ref: str | None,
    detected_ref: str | None,
    default_branch: str,
) -> str:
    if ref_type not in {"default", "branch", "tag", "commit"}:
        raise ValueError(f"Unsupported ref type: {ref_type}")
    if ref_type == "default":
        return default_branch
    selected = (explicit_ref or detected_ref or "").strip()
    if not selected:
        raise ValueError(f"{ref_type} ref is required")
    return selected


def _headers(credential: GitCredential) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AstrBot-Community-Plugin-Registry",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = (credential.temporary_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _url_opener(proxy_url: str | None):
    proxy_url = (proxy_url or "").strip()
    if not proxy_url:
        return urllib.request.build_opener()
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    )


def _github_error_message(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()
    message = payload.get("message")
    return str(message).strip() if message else raw.strip()


def _github_access_denied_message(status_code: int, message: str) -> str:
    lowered = message.lower()
    if status_code == 401:
        return "GitHub token is invalid or expired; check the token value"
    if "rate limit" in lowered:
        return "GitHub API rate limit exceeded; add a token or wait before retrying"
    if "resource not accessible by personal access token" in lowered:
        return "GitHub token cannot access this repository; grant repository Contents read permission"
    if "bad credentials" in lowered:
        return "GitHub token is invalid or expired; check the token value"
    if message:
        return f"GitHub access was denied: {message}"
    return "GitHub access was denied; check the token permissions"


def _decode_github_content(payload: dict[str, Any]) -> str:
    if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
        raise GitError("GitHub metadata.yaml response was not base64 file content")
    try:
        return base64.b64decode(payload["content"]).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise GitError("Failed to decode metadata.yaml from GitHub") from exc


def _metadata_preview(content: str) -> dict[str, Any]:
    metadata = parse_metadata_yaml_text(content)
    return {
        "name": metadata.name,
        "plugin_key": infer_plugin_key(metadata.name),
        "display_name": metadata.display_name,
        "desc": metadata.desc or "",
        "author": metadata.author,
        "version": metadata.version,
        "repo": metadata.repo,
        "tags": metadata.tags,
        "astrbot_version": metadata.astrbot_version,
    }


def _commit_info(payload: dict[str, Any]) -> dict[str, Any]:
    commit = payload.get("commit") if isinstance(payload.get("commit"), dict) else {}
    author = commit.get("author") if isinstance(commit.get("author"), dict) else {}
    message = str(commit.get("message") or "").splitlines()[0] if commit else None
    return {
        "sha": str(payload.get("sha") or ""),
        "message": message,
        "author_name": author.get("name"),
        "committed_at": _parse_datetime(author.get("date")),
    }


def _commit_sha_from_refs(
    ref_type: str,
    selected_ref: str,
    default_branch: str,
    branches: list[dict[str, Any]],
    tags: list[dict[str, Any]],
) -> str:
    if ref_type == "default":
        selected_ref = default_branch
        refs = branches
    elif ref_type == "branch":
        refs = branches
    elif ref_type == "tag":
        refs = tags
    else:
        return ""
    for item in refs:
        if item.get("name") == selected_ref and isinstance(item.get("commit_sha"), str):
            return str(item["commit_sha"])
    return ""


def _branch_options(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    options = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        commit = item.get("commit") if isinstance(item.get("commit"), dict) else {}
        name = item.get("name")
        sha = commit.get("sha")
        if isinstance(name, str) and isinstance(sha, str):
            options.append({"name": name, "commit_sha": sha, "protected": bool(item.get("protected"))})
    return options


def _tag_options(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    options = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        commit = item.get("commit") if isinstance(item.get("commit"), dict) else {}
        name = item.get("name")
        sha = commit.get("sha")
        if isinstance(name, str) and isinstance(sha, str):
            options.append({"name": name, "commit_sha": sha, "protected": False})
    return options


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
