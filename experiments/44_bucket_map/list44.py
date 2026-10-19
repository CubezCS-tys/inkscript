"""Experiment 44: full read-only listing of the owner's S3 buckets.

Only ListObjectsV2 is called (no GET, no copy, no delete). Each shard (a key prefix of one bucket) is paginated
1,000 keys per request and every page is appended to out/listing/<bucket>__<shard>.tsv (key, size, last-modified,
storage class) as it arrives; the continuation token is saved after each page in a .state file, so a dropped
connection resumes where it stopped. Request counts land in out/listing/requests.json.

    .venv/bin/python experiments/44_bucket_map/list44.py            # all shards, 8 threads
"""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import awscli.clidriver  # noqa: F401  (the venv's aws CLI vendors botocore; importing it makes botocore importable)
import botocore.session
from botocore.config import Config

HERE = Path(__file__).resolve().parent
OUT = HERE / "out" / "listing"
OUT.mkdir(parents=True, exist_ok=True)

SRC = "mandumah-source-docs"
QDR = "mandumah-qdrant-backups"
TRAIL = "aws-cloudtrail-logs-006127064053-14137c60"
REGION = {SRC: "eu-north-1", QDR: "eu-west-1", TRAIL: "eu-north-1"}

# The main bucket's document folders start with a digit; split them by first two digits for parallel listing.
SHARDS = [(SRC, f"{a}{b}") for a in "0123456789" for b in "0123456789"]
SHARDS += [(SRC, "legacy/"), (SRC, "legacy-test/"), (SRC, "metadata/"), (QDR, "mysql/"), (QDR, "qdrant/"),
           (TRAIL, "AWSLogs/")]

_lock = threading.Lock()
_clients = {}


def client(bucket):
    with _lock:
        if bucket not in _clients:
            s = botocore.session.Session()
            _clients[bucket] = s.create_client("s3", region_name=REGION[bucket],
                                               config=Config(retries={"max_attempts": 10, "mode": "adaptive"},
                                                             max_pool_connections=20))
        return _clients[bucket]


def shard(bucket, prefix):
    name = f"{bucket}__{prefix.replace('/', '_') or 'ROOT'}"
    tsv, state = OUT / f"{name}.tsv", OUT / f"{name}.state"
    st = json.loads(state.read_text()) if state.exists() else {"token": None, "done": False, "requests": 0, "keys": 0}
    if st["done"]:
        return name, st
    if st["token"] is None and tsv.exists():
        tsv.unlink()                                           # restarted before the first page was saved
    c = client(bucket)
    while True:
        kw = dict(Bucket=bucket, Prefix=prefix, MaxKeys=1000)
        if st["token"]:
            kw["ContinuationToken"] = st["token"]
        r = c.list_objects_v2(**kw)
        rows = [f"{o['Key']}\t{o['Size']}\t{o['LastModified'].isoformat()}\t{o.get('StorageClass', '')}\n"
                for o in r.get("Contents", [])]
        with tsv.open("a") as f:
            f.writelines(rows)
        st["requests"] += 1
        st["keys"] += len(rows)
        st["token"] = r.get("NextContinuationToken")
        if not r.get("IsTruncated"):
            st["done"], st["token"] = True, None
        state.write_text(json.dumps(st))
        if st["done"]:
            return name, st


def root_files():
    """Keys sitting at the root of each bucket (no folder)."""
    res = {}
    for b in REGION:
        r = client(b).list_objects_v2(Bucket=b, Delimiter="/", MaxKeys=1000, StartAfter="")
        # Root files of the main bucket sort after the 1M digit folders, so ask from a point past them too.
        keys = [(o["Key"], o["Size"], o["LastModified"].isoformat()) for o in r.get("Contents", [])]
        n = 1
        if b == SRC:
            r2 = client(b).list_objects_v2(Bucket=b, Delimiter="/", MaxKeys=1000, StartAfter="9999")
            keys += [(o["Key"], o["Size"], o["LastModified"].isoformat()) for o in r2.get("Contents", [])]
            res["src_top_prefixes_after_digits"] = [p["Prefix"] for p in r2.get("CommonPrefixes", [])]
            n += 1
        res[b] = {"files": sorted(set(keys)), "requests": n}
    (OUT / "root_files.json").write_text(json.dumps(res, indent=1))
    return res


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    root_files()
    with ThreadPoolExecutor(workers) as ex:
        for name, st in ex.map(lambda s: shard(*s), SHARDS):
            print(name, st["keys"], st["requests"], flush=True)
    req = {p.stem: json.loads(p.read_text())["requests"] for p in OUT.glob("*.state")}
    (OUT / "requests.json").write_text(json.dumps({"total": sum(req.values()) + 4, "per_shard": req}, indent=1))
    print("requests", sum(req.values()) + 4)


if __name__ == "__main__":
    main()
