#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
commit_and_push.py —— 提交本仓库改动并推送到 Gitea
=====================================================

约定（用户 2026-10-12 定）：
  改动完成后**先提醒用户确认**；用户确认后才用本脚本提交并推送。

用法：
    python scripts/commit_and_push.py                 # 预览：只列出待提交改动
    python scripts/commit_and_push.py -m "提交说明"    # 提交 + 推送
    python scripts/commit_and_push.py -m "说明" --no-push   # 只提交，不推送

设计要点：
  * token 从 `D:/aiwork/services/credentials.env` 的 `GITEA_TOKEN` 读，
    用 `git -c http.extraheader=Authorization: token <T>` 传入 —— **不落进 .git/config**。
  * 网络操作前**剔除代理环境变量**（Bash 工具恒注入 http_proxy，
    会让 git 看到「代理的假 502」）。
  * 双通道故障切换：主 DDNSTO → 备 节点小宝（与技能库同步同一套通道）。
    **每次网络操作都从主通道开始试**，主恢复后自动切回。
"""
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

PROXY_KEYS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
              "all_proxy", "ALL_PROXY")


def read_token():
    """环境变量优先，其次凭据文件。都没有则报错退出。"""
    tok = os.environ.get("GITEA_TOKEN", "").strip()
    if tok:
        return tok
    if CRED.is_file():
        with open(CRED, encoding="utf-8", errors="replace") as f:
            for ln in f:
                if ln.startswith("GITEA_TOKEN="):
                    return ln.split("=", 1)[1].strip()
    return ""


def git(args, token=None, timeout=90):
    cmd = ["git", "-C", str(REPO)]
    if token:
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


def main():
    argv = sys.argv[1:]
    msg = None
    if "-m" in argv:
        i = argv.index("-m")
        if i + 1 < len(argv):
            msg = argv[i + 1]
    no_push = "--no-push" in argv

    print("仓库：%s" % REPO)
    print("远端：%s%s" % (CHANNEL_BASES[0], origin_path()))
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

    print("推送中 …")
    rc, out, err = git_net(["push", "origin", BRANCH], token, "push")
    if rc != 0:
        print("!! 推送失败：%s" % (err or out))
        return 1
    print("✅ 推送成功")
    if out:
        for ln in out.splitlines():
            print("   " + ln)

    rc, out, _ = git(["rev-list", "--left-right", "--count",
                      "origin/%s...HEAD" % BRANCH])
    if rc == 0:
        print("   与远端差异（behind ahead）：%s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
