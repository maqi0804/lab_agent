"""修复被亿赛通 (EsafeNet Cobra DocGuard) 加密的 dist-info/RECORD。

背景
----
本机安装了亿赛通加密客户端，它有两条独立规则：
  1. 按扩展名加密（如 .txt）；
  2. 对 rename / os.replace 操作重新套用加密策略。

pip 写 RECORD 用的是 `adjacent_tmp_file` + `os.replace`，正好命中规则 2，
于是每个 pip 安装的包，RECORD 都会变成密文（文件头 b'b\\x14#e' + 'E-SafeNet'）。
pip 卸载时要 `read_text('RECORD')`，遇到密文直接抛 UnicodeDecodeError。

解法
----
直接 open().write()（不走 rename）写出去的文件不会被加密。
本脚本扫描 site-packages，把密文 RECORD 按"该包实际存在的文件"重建为明文。

安全边界
--------
- 只列出磁盘上真实存在的文件，不会指向不存在的路径；
- 共享命名空间（google / opentelemetry）只列明确属于自己的子路径，
  卸载时其余文件会残留，但绝不会误删其他包的文件；
- 原始密文 RECORD 备份在 site-packages 同级的 _record_bak/ 下。

用法
----
    .venv/Scripts/python.exe tools/fix_pip_record.py            # 修复全部
    .venv/Scripts/python.exe tools/fix_pip_record.py --dry-run  # 只看不改
    .venv/Scripts/python.exe tools/fix_pip_record.py --force    # 连明文也重建

每次 `pip install` 之后跑一次即可。
"""

from __future__ import annotations

import argparse
import collections
import glob
import os
import re
import shutil
import sys
import sysconfig

MAGIC = b"b\x14#e"  # E-SafeNet 密文头

# 包名(norm 后) -> 真实顶层目录/文件，用于包名与导入名不一致的情况
TOPLEVEL_FIX = {
    "pyyaml": ["yaml"],
    "python_dateutil": ["dateutil"],
    "python_dotenv": ["dotenv"],
    "pyjwt": ["jwt"],
    "scikit_learn": ["sklearn"],
    "markdown_it_py": ["markdown_it"],
    "websocket_client": ["websocket"],
    "rpds_py": ["rpds"],
    "grpcio": ["grpc"],
    "attrs": ["attr", "attrs"],
    "pillow": ["PIL"],
}

# 共享命名空间：只列明确属于自己的子路径
NAMESPACE_SUBSET = {
    "opentelemetry_api": [
        "opentelemetry/*.py", "opentelemetry/py.typed", "opentelemetry/_logs",
        "opentelemetry/attributes", "opentelemetry/baggage", "opentelemetry/context",
        "opentelemetry/environment_variables", "opentelemetry/metrics",
        "opentelemetry/propagate", "opentelemetry/propagators", "opentelemetry/trace",
        "opentelemetry/util", "opentelemetry/version",
    ],
    "opentelemetry_sdk": ["opentelemetry/sdk"],
    "opentelemetry_proto": ["opentelemetry/proto"],
    "opentelemetry_semantic_conventions": ["opentelemetry/semconv"],
    "protobuf": ["google/protobuf", "google/_upb"],
    "googleapis_common_protos": [
        "google/api", "google/rpc", "google/type", "google/logging",
        "google/longrunning", "google/cloud", "google/gapic",
    ],
}

# 多个发行版共用同一目录且无法安全切分，只清理自己的 dist-info
DISTINFO_ONLY = {
    "opentelemetry_exporter_otlp_common",
    "opentelemetry_exporter_otlp_proto_common",
    "opentelemetry_exporter_otlp_proto_grpc",
}


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def dist_name(distinfo: str) -> str:
    path = os.path.join(distinfo, "METADATA")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("Name:"):
                    return line.split(":", 1)[1].strip()
                if not line.strip():
                    break
    except OSError:
        pass
    return ""


def walk_files(base: str) -> list[str]:
    return [
        os.path.join(root, f).replace("\\", "/")
        for root, _, files in os.walk(base)
        for f in files
    ]


def add_path(entries: set[str], pattern: str) -> None:
    if "*" in pattern:
        for hit in glob.glob(pattern):
            if os.path.isdir(hit):
                entries.update(walk_files(hit))
            elif os.path.isfile(hit):
                entries.add(hit)
    elif os.path.isdir(pattern):
        entries.update(walk_files(pattern))
    elif os.path.isfile(pattern):
        entries.add(pattern)


def build_entries(distinfo: str, name: str, shared: set[str]) -> list[str]:
    entries: set[str] = set(walk_files(distinfo))
    key = norm(name)

    if key in NAMESPACE_SUBSET:
        for p in NAMESPACE_SUBSET[key]:
            add_path(entries, p)
        return sorted(x for x in entries if os.path.exists(x))

    if key in DISTINFO_ONLY:
        return sorted(x for x in entries if os.path.exists(x))

    candidates = list(TOPLEVEL_FIX.get(key, []))
    candidates.append(key)
    tl = os.path.join(distinfo, "top_level.txt")
    if os.path.exists(tl):
        with open(tl, encoding="utf-8", errors="replace") as fh:
            for n in fh.read().split():
                if n not in candidates:
                    candidates.append(n)

    for c in candidates:
        if not c or c in shared:
            continue
        if os.path.isdir(c):
            entries.update(walk_files(c))
        elif os.path.isfile(f"{c}.py"):
            entries.add(f"{c}.py")
        else:
            entries.update(glob.glob(f"{c}*.pyd"))

    return sorted(x for x in entries if os.path.exists(x))


def main() -> int:
    ap = argparse.ArgumentParser(description="修复被加密的 dist-info/RECORD")
    ap.add_argument("--site-packages", default=None, help="默认取当前解释器的 purelib")
    ap.add_argument("--dry-run", action="store_true", help="只检测不写入")
    ap.add_argument("--force", action="store_true", help="连明文 RECORD 也重建")
    args = ap.parse_args()

    sp = args.site_packages or sysconfig.get_paths()["purelib"]
    os.chdir(sp)
    backup = os.path.join(os.path.dirname(sp), "_record_bak")
    os.makedirs(backup, exist_ok=True)

    dists = sorted(glob.glob("*.dist-info"))
    names = {d: dist_name(d) for d in dists}
    counter = collections.Counter(
        n for d in dists
        for n in _declared(d)
    )
    shared = {n for n, c in counter.items() if c > 1}

    fixed, skipped, total = [], 0, 0
    for d in dists:
        record = os.path.join(d, "RECORD")
        if not os.path.exists(record):
            continue
        raw = open(record, "rb").read(4)
        encrypted = raw == MAGIC
        if not encrypted and not args.force:
            skipped += 1
            continue
        if args.dry_run:
            fixed.append((names[d], "<dry-run>", encrypted))
            continue

        bak = os.path.join(backup, f"{d}__RECORD.bak")
        if not os.path.exists(bak):
            shutil.copy2(record, bak)

        entries = build_entries(d, names[d], shared)
        total += len(entries)
        with open(record, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(f"{p},," for p in entries) + "\n")
        fixed.append((names[d], len(entries), encrypted))

    mode = "待修复" if args.dry_run else "已修复"
    print(f"site-packages: {sp}")
    print(f"扫描 {len(dists)} 个包，{mode} {len(fixed)} 个，跳过(明文) {skipped} 个")
    if not args.dry_run:
        print(f"写入条目合计 {total}")
    for name, n, enc in fixed:
        flag = "密文" if enc else "明文"
        print(f"  {name:42s} {str(n):>6s}  [{flag}]")
    return 0


def _declared(distinfo: str) -> list[str]:
    tl = os.path.join(distinfo, "top_level.txt")
    if not os.path.exists(tl):
        return []
    with open(tl, encoding="utf-8", errors="replace") as fh:
        return fh.read().split()


if __name__ == "__main__":
    sys.exit(main())
