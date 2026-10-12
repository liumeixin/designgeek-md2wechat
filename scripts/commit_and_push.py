#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
commit_and_push.py —— 提交本仓库改动，推送到 Gitea，并镜像到 GitHub
=====================================================================

约定（用户 2026-10-12 定）：
  改动完成后**先提醒用户确认**；用户确认后才用本脚本提交并推送。

用法：
    python scripts/commit_and_push.py                 # 预览：只列出待提交改动
    python scripts/commit_and_push.py -m "提交说明"    # 提交 + 推 Gitea + 推 GitHub
    python scripts/commit_and_push.py -m "说明" --no-push     # 只提交，不推送
    python scripts/commit_and_push.py -m "说明" --no-github   # 推 Gitea，跳过 GitHub

为什么有两个远端（2026-10-12 起）：
  * `origin` = Gitea `Agent/designgeek-md2wechat` —— **权威源**，octop(NAS) 从这里拉。
  * `github` = GitHub `liumeixin/designgeek-md2wechat`（public）—— **镜像**，
    push 到它的 `main` 会触发 `.github/workflows/docker-publish.yml`，
    构建并发布 `ghcr.io/liumeixin/designgeek-md2wechat:latest`。
  ⚠️ 不推 GitHub ⇒ 镜像不会重建（2026-10-12 之前就断在这儿：镜像停在 2026-05-31）。

设计要点：
  * Gitea token 从 `D:/aiwork/services/credentials.env` 的 `GITEA_TOKEN` 读，
    用 `git -c http.extraheader=Authorization: token <T>` 传入 —— **不落进 .git/config**。
  * GitHub token 从同一文件的 `GITHUB_TOKEN` 读，用 `Authorization: Basic base64(user:token)`。
  * 网络操作前**剔除代理环境变量**（Bash 工具恒注入 http_proxy，
    会让 git 看到「代理的假 502」）。
  * Gitea 双通道故障切换：主 DDNSTO → 备 节点小宝（与技能库同步同一套通道）。
    **每次网络操作都从主通道开始试**，主恢复后自动切回。
  * GitHub 推送失败**不影响** Gitea 推送结果（Gitea 是权威源，先推它）。
  * GitHub 推送失败时**自动改走官方 Git Data API 兜底**（见下）。
    github.com 的 HTTPS 在本机是**间歇性不可达**的（TCP 能连、TLS 握手超时，
    而 api.github.com 一直正常），`git push` 因此会随机失败。API 兜底会把提交
    **逐字节复刻**到远端 —— author/committer/时间/message/tree 全对齐时生成的
    commit SHA 与本地完全相同，远端不会与本地分叉，后续 git push 依旧正常。
"""
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CRED = Path(r"D:/aiwork/services/credentials.env")

# 双通道（顺序即优先级）。两者指向**同一个 Gitea 实例**，只是通路不同。
CHANNEL_BASES = (
    "https://dx4700-gitea.tocmcc.cn",   # 主：DDNSTO
    "https://dx4700-gitea.iepose.cn",   # 备：节点小宝（2 Mbps / 1014 MB 每月）
)
DEFAULT_REPO_PATH = "/Agent/designgeek-md2wechat.git"
BRANCH = "main"

# GitHub 镜像 remote（触发 Actions 构建 ghcr.io 镜像）
GITHUB_REMOTE = "github"
GITHUB_OWNER_FALLBACK = "liumeixin"

PROXY_KEYS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
              "all_proxy", "ALL_PROXY")


def read_cred(key):
    """环境变量优先，其次凭据文件。都没有则返回空串。"""
    val = os.environ.get(key, "").strip()
    if val:
        return val
    if CRED.is_file():
        with open(CRED, encoding="utf-8", errors="replace") as f:
            for ln in f:
                if ln.startswith(key + "="):
                    return ln.split("=", 1)[1].strip()
    return ""


def read_token():
    return read_cred("GITEA_TOKEN")


def git(args, token=None, timeout=90, header=None, raw=False):
    cmd = ["git", "-C", str(REPO)]
    if header:
        cmd += ["-c", "http.extraheader=%s" % header]
    elif token:
        cmd += ["-c", "http.extraheader=Authorization: token %s" % token]
    cmd += list(args)
    env = os.environ.copy()
    for k in PROXY_KEYS:
        env.pop(k, None)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
        if raw:
            return r.returncode, r.stdout, r.stderr
        return (r.returncode,
                r.stdout.decode("utf-8", errors="replace").strip(),
                r.stderr.decode("utf-8", errors="replace").strip())
    except subprocess.TimeoutExpired:
        return 124, (b"" if raw else ""), (b"timeout" if raw else "timeout")
    except OSError as e:
        return 125, (b"" if raw else ""), (str(e).encode() if raw else str(e))


def origin_path():
    """取当前 origin 的仓库路径（/Agent/xxx.git）——只换通道域名，不换仓库路径。"""
    rc, out, _ = git(["remote", "get-url", "origin"])
    if rc == 0 and out:
        m = re.search(r"(/[^/\s]+/[^/\s]+?\.git)$", out)
        if m:
            return m.group(1)
    return DEFAULT_REPO_PATH


def git_net(args, token, what):
    """网络操作：按 CHANNEL_BASES 顺序做通道故障切换。"""
    path = origin_path()
    last = (1, "", "all channels failed")
    for idx, base in enumerate(CHANNEL_BASES):
        url = base + path
        rc, cur, _ = git(["remote", "get-url", "origin"])
        if rc != 0 or cur.strip() != url:
            rc2, _, err2 = git(["remote", "set-url", "origin", url])
            if rc2 != 0:
                print("  !! 切换通道失败：%s" % err2[:150])
                continue
        rc, out, err = git(args, token=token)
        if rc == 0:
            if idx > 0:
                print("  ℹ %s 主通道不可用，已自动切到**备用通道**（%s）"
                      % (what, base.split("/")[2]))
            return rc, out, err
        last = (rc, out, err)
        print("  !! %s 通道失败 %s (rc=%d)：%s"
              % (what, base.split("/")[2], rc,
                 (err or out).replace("\n", " | ")[:200]))
    return last


def github_owner():
    """从 github remote 的 URL 里取 owner；取不到用兜底值。"""
    rc, out, _ = git(["remote", "get-url", GITHUB_REMOTE])
    if rc == 0 and out:
        m = re.search(r"github\.com[:/]+([^/]+)/", out)
        if m:
            return m.group(1)
    return ""


# ── GitHub Git Data API 兜底通道 ────────────────────────────────────────────
# 为什么需要：github.com 的 443 在本机是**间歇性不可达**（TCP 能连上、
# TLS/HTTP 层被阻断；`api.github.com` 却始终正常）。`git push` 因此会随机
# 报 "Empty reply from server" / "Failed to connect ... 21 s"。
# 兜底做法：用官方 Git Data API 建 blob → tree → commit → 更新 ref。
# 只要 author / committer / 时间 / message / tree 与本地逐字节一致，
# 生成的 commit SHA 就与本地**完全相同** ⇒ 远端不分叉，后续 git push 正常。

API_BASE = "https://api.github.com"


def _api(method, path, tok, body=None, timeout=45):
    """调 api.github.com。返回 (status, 解析后的 json 或原始文本)。"""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(API_BASE + path, data=data, method=method, headers={
        "Authorization": "Bearer %s" % tok,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "designgeek-md2wechat-push",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    # 显式清空代理：Bash 工具注入的 http_proxy 会让请求打到本地假代理上
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def _repo_slug():
    """从 github remote URL 解析 (owner, repo)；解析不出返回 (None, None)。"""
    rc, url, _ = git(["remote", "get-url", GITHUB_REMOTE])
    if rc != 0 or not url or "github.com" not in url:
        return None, None
    tail = url.split("github.com", 1)[1].lstrip("/:").rstrip("/")
    parts = [p for p in tail.split("/") if p]
    if len(parts) < 2:
        return None, None
    return parts[0], re.sub(r"\.git$", "", parts[1])


def _commit_meta(sha):
    """读本地提交对象原文，解析出 tree/parents/author/committer/message。

    message 保持**原始字节**（含尾部换行），否则复刻出的 SHA 会对不上。
    """
    rc, raw, err = git(["cat-file", "commit", sha], raw=True)
    if rc != 0:
        raise RuntimeError("读不到提交对象 %s：%s" % (sha[:7], err))
    head, _, message = raw.partition(b"\n\n")
    info = {"tree": None, "parent": [], "author": None, "committer": None}
    for line in head.decode("utf-8", "replace").splitlines():
        k, _, v = line.partition(" ")
        if k == "tree":
            info["tree"] = v
        elif k == "parent":
            info["parent"].append(v)
        elif k in ("author", "committer"):
            info[k] = v
    try:
        info["message"] = message.decode("utf-8")
    except UnicodeDecodeError:
        raise RuntimeError("提交 %s 的 message 不是 UTF-8，API 兜底无法处理" % sha[:7])
    return info


def _person(line):
    """`Name <mail> 1700000000 +0800` → (name, mail, ISO 时间串)。"""
    m = re.match(r"^(.*?) <(.*?)> (\d+) ([+-]\d{4})$", line)
    if not m:
        raise RuntimeError("无法解析提交身份：%s" % line)
    name, mail, ts, off = m.group(1), m.group(2), int(m.group(3)), m.group(4)
    sign = 1 if off[0] == "+" else -1
    delta = timedelta(hours=int(off[1:3]), minutes=int(off[3:5])) * sign
    return name, mail, datetime.fromtimestamp(ts, tz=timezone(delta)).isoformat()


def _tree_entries(parent, commit):
    """列出 commit 相对 parent 的变更：[(状态, 路径), ...]。

    用 --no-renames，让「重命名」退化成 删除+新增，省掉 R/C 状态的处理。
    """
    rc, out, err = git(["diff-tree", "-r", "--name-status", "-z",
                        "--no-renames", parent, commit], raw=True)
    if rc != 0:
        raise RuntimeError("diff-tree 失败：%s" % err)
    parts = out.split(b"\0")
    res, i = [], 0
    while i + 1 < len(parts):
        st = parts[i].decode("utf-8", "replace").strip()
        path = parts[i + 1].decode("utf-8", "replace")
        if st:
            res.append((st[0], path))
        i += 2
    return res


def push_github_via_api(tok, owner):
    """用 Git Data API 把本地 main 复刻到 GitHub。成功返回 True。

    前置：远端 main 必须是本地 HEAD 的祖先（否则会分叉，直接拒绝）。
    """
    owner2, name = _repo_slug()
    owner = owner2 or owner
    if not (owner and name):
        raise RuntimeError("解析不出 GitHub owner/repo")

    rc, head, _ = git(["rev-parse", "HEAD"])
    if rc != 0:
        raise RuntimeError("读不到本地 HEAD")
    head = head.strip()

    st, d = _api("GET", "/repos/%s/%s/git/ref/heads/%s" % (owner, name, BRANCH), tok)
    if st == 404:
        print("     （远端还没有 %s 分支，将以空 base 创建）" % BRANCH)
        remote_sha = None
    elif st != 200:
        raise RuntimeError("读远端 ref 失败 HTTP %s：%s" % (st, str(d)[:200]))
    else:
        remote_sha = d["object"]["sha"]

    if remote_sha == head:
        print("     远端已是最新（%s），无需复刻" % head[:7])
        return True

    if remote_sha:
        rc, _, _ = git(["merge-base", "--is-ancestor", remote_sha, head])
        if rc != 0:
            raise RuntimeError(
                "远端 %s 不是本地 HEAD 的祖先 ⇒ 会分叉，拒绝用 API 复刻。"
                "请先人工处理分叉。" % remote_sha[:7])
        rc, out, _ = git(["rev-list", "--reverse", "%s..%s" % (remote_sha, head)])
        todo = [x for x in out.splitlines() if x.strip()]
    else:
        rc, out, _ = git(["rev-list", "--reverse", head])
        todo = [x for x in out.splitlines() if x.strip()]

    print("     远端 %s → 本地 %s，待复刻 %d 个提交"
          % ((remote_sha or "(空)")[:7], head[:7], len(todo)))

    base_sha = remote_sha
    for n, sha in enumerate(todo, 1):
        meta = _commit_meta(sha)

        # base tree = 上一个复刻出的 commit 的 tree（首个 = 远端当前 tree）
        if base_sha:
            st, d = _api("GET", "/repos/%s/%s/git/commits/%s" % (owner, name, base_sha), tok)
            if st != 200:
                raise RuntimeError("读远端 tree 失败 HTTP %s" % st)
            base_tree = d["tree"]["sha"]
        else:
            base_tree = None

        entries = []
        for status, path in _tree_entries(base_sha or "4b825dc642cb6eb9a060e54bf8d69288fbee4904", sha):
            if status == "D":
                entries.append({"path": path, "mode": "100644",
                                "type": "blob", "sha": None})
                continue
            rc, ls, _ = git(["ls-tree", sha, "--", path])
            if rc != 0 or not ls:
                raise RuntimeError("取 %s:%s 的 mode 失败" % (sha[:7], path))
            mode = ls.split()[0]
            if mode == "160000":                      # submodule：直接引用其 commit
                rc, sub, _ = git(["rev-parse", "%s:%s" % (sha, path)])
                entries.append({"path": path, "mode": mode,
                                "type": "commit", "sha": sub.strip()})
                continue
            rc, content, _ = git(["cat-file", "blob", "%s:%s" % (sha, path)], raw=True)
            if rc != 0:
                raise RuntimeError("读 blob %s:%s 失败" % (sha[:7], path))
            st, d = _api("POST", "/repos/%s/%s/git/blobs" % (owner, name), tok,
                         {"content": base64.b64encode(content).decode(),
                          "encoding": "base64"})
            if st != 201:
                raise RuntimeError("建 blob 失败 HTTP %s：%s" % (st, str(d)[:200]))
            entries.append({"path": path, "mode": mode,
                            "type": "blob", "sha": d["sha"]})

        tree_body = {"tree": entries}
        if base_tree:
            tree_body["base_tree"] = base_tree
        st, d = _api("POST", "/repos/%s/%s/git/trees" % (owner, name), tok, tree_body)
        if st != 201:
            raise RuntimeError("建 tree 失败 HTTP %s：%s" % (st, str(d)[:200]))
        new_tree = d["sha"]
        if new_tree != meta["tree"]:
            raise RuntimeError("tree 不一致（本地 %s / 远端生成 %s）⇒ 放弃"
                               % (meta["tree"][:12], new_tree[:12]))

        a_name, a_mail, a_date = _person(meta["author"])
        c_name, c_mail, c_date = _person(meta["committer"])
        st, d = _api("POST", "/repos/%s/%s/git/commits" % (owner, name), tok, {
            "message": meta["message"],
            "tree": new_tree,
            "parents": [base_sha] if base_sha else [],
            "author": {"name": a_name, "email": a_mail, "date": a_date},
            "committer": {"name": c_name, "email": c_mail, "date": c_date},
        })
        if st != 201:
            raise RuntimeError("建 commit 失败 HTTP %s：%s" % (st, str(d)[:300]))
        new_commit = d["sha"]
        if new_commit != sha:
            raise RuntimeError("commit SHA 不一致（本地 %s / 远端生成 %s）⇒ 放弃，"
                               "避免制造分叉" % (sha[:7], new_commit[:7]))
        print("     [%d/%d] %s %s ✅" % (n, len(todo), sha[:7],
                                         meta["message"].splitlines()[0][:44]))
        base_sha = new_commit

    st, d = _api("PATCH", "/repos/%s/%s/git/refs/heads/%s" % (owner, name, BRANCH),
                 tok, {"sha": base_sha, "force": False})
    if st not in (200, 201):
        raise RuntimeError("更新 ref 失败 HTTP %s：%s" % (st, str(d)[:300]))

    # 顺手更新本地的远端跟踪引用，免得 git status / ls-remote 显示过期
    git(["update-ref", "refs/remotes/%s/%s" % (GITHUB_REMOTE, BRANCH), base_sha])
    return True


def push_github(what="push-github"):
    """把当前分支推到 GitHub 镜像 remote（触发 Actions 重建镜像）。

    返回 True / False / None：
      None  = 没配 github remote，跳过（不算失败）
      False = 配了但推失败（token 缺失 / 网络 / 非快进）
    """
    rc, url, _ = git(["remote", "get-url", GITHUB_REMOTE])
    if rc != 0 or not url:
        print("  ℹ 未配置 GitHub remote（%s），跳过镜像推送" % GITHUB_REMOTE)
        return None

    tok = read_cred("GITHUB_TOKEN")
    if not tok:
        print("  !! GITHUB_TOKEN 缺失（环境变量与 %s 都没有）" % CRED)
        print("     ⇒ GitHub 镜像未更新，**ghcr.io 镜像不会重建**")
        return False

    owner = github_owner() or GITHUB_OWNER_FALLBACK
    repo_name = re.sub(r"\.git$", "", url.rstrip("/").split("/")[-1])
    actions_url = "https://github.com/%s/%s/actions" % (owner, repo_name)
    header = "Authorization: Basic %s" % base64.b64encode(
        ("%s:%s" % (owner, tok)).encode()).decode()

    rc, out, err = git(["push", GITHUB_REMOTE, BRANCH], header=header, timeout=180)
    blob = (out + "\n" + err).strip()

    if rc == 0:
        if "Everything up-to-date" in blob:
            print("  ℹ GitHub 镜像无待推送改动")
        else:
            print("  ✅ GitHub 镜像已推送: %s" % blob.replace("\n", " | ")[:200])
            print("     ⇒ 已触发 Actions，稍后可在 %s 看构建" % actions_url)
        return True

    # ── git push 失败 → API 兜底 ────────────────────────────────────────
    print("  !! %s 失败：%s" % (what, blob.replace("\n", " | ")[:300]))
    print("     ⇒ Gitea 已推成功（权威源没问题）。")
    print("  ↻ github.com 的 HTTPS 在本机常被阻断，改用 GitHub Git Data API 兜底…")
    try:
        if push_github_via_api(tok, owner):
            print("  ✅ 已通过 Git Data API 复刻到 GitHub（commit SHA 与本地一致）")
            print("     ⇒ 已触发 Actions，稍后可在 %s 看构建" % actions_url)
            return True
    except Exception as e:
        print("  !! API 兜底也失败：%s" % e)

    print("     ⇒ GitHub 镜像没更新，**ghcr.io 镜像不会重建**"
          "（Gitea 权威源不受影响）。")
    return False


def main():
    argv = sys.argv[1:]
    msg = None
    if "-m" in argv:
        i = argv.index("-m")
        if i + 1 < len(argv):
            msg = argv[i + 1]
    no_push = "--no-push" in argv
    no_github = "--no-github" in argv

    print("仓库：%s" % REPO)
    print("Gitea ：%s%s" % (CHANNEL_BASES[0], origin_path()))
    rc, ghurl, _ = git(["remote", "get-url", GITHUB_REMOTE])
    print("GitHub：%s" % (ghurl if rc == 0 and ghurl else "（未配置，将跳过）"))
    print()

    rc, out, _ = git(["status", "--short"])
    if rc != 0:
        print("!! 无法读取 git 状态，确认这是不是一个 git 仓库")
        return 2
    dirty = out.strip()

    # ── 预览模式 ────────────────────────────────────────────────────────
    if not msg:
        if not dirty:
            print("✅ 工作区干净，没有待提交的改动。")
            return 0
        print("待提交的改动：")
        for ln in dirty.splitlines():
            print("  " + ln)
        print()
        rc, stat, _ = git(["diff", "--stat", "HEAD"])
        if stat:
            print("改动统计：")
            print(stat)
        print()
        print("（预览模式，未写任何东西；确认后加 -m \"提交说明\" 执行提交）")
        return 0

    # ── 提交 ────────────────────────────────────────────────────────────
    if not dirty:
        print("✅ 工作区干净，无需提交。")
    else:
        rc, out, err = git(["add", "-A"])
        if rc != 0:
            print("!! git add 失败：%s" % err)
            return 2
        rc, out, err = git(["commit", "-m", msg])
        if rc != 0:
            print("!! git commit 失败：%s" % (err or out))
            return 2
        print("✅ 已提交：%s" % out.splitlines()[0])

    # ── 推送 ────────────────────────────────────────────────────────────
    if no_push:
        print("（--no-push，跳过推送）")
        return 0

    token = read_token()
    if not token:
        print("!! 凭据缺失：环境变量 GITEA_TOKEN 与 %s 里都没有，已停止。" % CRED)
        return 2

    print("① 推送 Gitea（权威源）…")
    rc, out, err = git_net(["push", "origin", BRANCH], token, "push")
    if rc != 0:
        print("!! Gitea 推送失败：%s" % (err or out))
        return 1
    print("✅ Gitea 推送成功")
    if out:
        for ln in out.splitlines():
            print("   " + ln)

    rc, out, _ = git(["rev-list", "--left-right", "--count",
                      "origin/%s...HEAD" % BRANCH])
    if rc == 0:
        print("   与 Gitea 差异（behind ahead）：%s" % out)

    if no_github:
        print("（--no-github，跳过 GitHub 镜像推送 ⇒ 镜像不会重建）")
        return 0

    print("② 推送 GitHub 镜像（触发 ghcr.io 镜像重建）…")
    ok = push_github()
    if ok is False:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
