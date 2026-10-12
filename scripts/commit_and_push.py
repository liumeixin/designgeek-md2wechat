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
"""
import base64
import os
import re
import subprocess
import sys
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


def git(args, token=None, timeout=90, header=None):
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
        return (r.returncode,
                r.stdout.decode("utf-8", errors="replace").strip(),
                r.stderr.decode("utf-8", errors="replace").strip())
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as e:
        return 125, "", str(e)


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
    header = "Authorization: Basic %s" % base64.b64encode(
        ("%s:%s" % (owner, tok)).encode()).decode()

    rc, out, err = git(["push", GITHUB_REMOTE, BRANCH], header=header, timeout=180)
    blob = (out + "\n" + err).strip()
    if rc != 0:
        print("  !! %s 失败：%s" % (what, blob.replace("\n", " | ")[:300]))
        print("     ⇒ Gitea 已推成功（权威源没问题）；但 GitHub 镜像没更新。")
        return False
    if "Everything up-to-date" in blob:
        print("  ℹ GitHub 镜像无待推送改动")
    else:
        print("  ✅ GitHub 镜像已推送: %s" % blob.replace("\n", " | ")[:200])
        print("     ⇒ 已触发 Actions，稍后可在 "
              "https://github.com/%s/%s/actions 看构建"
              % (owner, re.sub(r"\.git$", "", url.rstrip("/").split("/")[-1])))
    return True


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
