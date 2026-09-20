#!/usr/bin/env python3
"""chunks 打包/解包 —— 用于 GitHub Release asset 存储"""
import os, sys, tarfile

D = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(D, "chunks")
ARCHIVE = os.path.join(D, "chunks.tar.gz")

def pack():
    if not os.path.isdir(SRC):
        print("no chunks/"); return 1
    n = 0
    with tarfile.open(ARCHIVE, "w:gz", compresslevel=9) as tar:
        for f in sorted(os.listdir(SRC)):
            if f.endswith(".json"):
                tar.add(os.path.join(SRC, f), arcname=f); n += 1
    print("packed %d files -> chunks.tar.gz (%.1fMB)" % (n, os.path.getsize(ARCHIVE)/1e6))
    return 0

def unpack():
    if not os.path.exists(ARCHIVE):
        print("no chunks.tar.gz"); return 1
    os.makedirs(SRC, exist_ok=True)
    with tarfile.open(ARCHIVE, "r:gz") as tar:
        tar.extractall(SRC)
    n = len([f for f in os.listdir(SRC) if f.endswith(".json")])
    print("unpacked %d files -> chunks/" % n)
    return 0

if __name__ == "__main__":
    sys.exit(pack() if (len(sys.argv) < 2 or sys.argv[1] == "pack") else unpack())
