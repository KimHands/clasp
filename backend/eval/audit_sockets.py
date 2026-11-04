"""
실제 백엔드와 실제 임베딩 모델로 스캔하며 백엔드 프로세스의 소켓 연결을 기록한다.
파일 내용이 루프백 밖으로 나가지 않는지 확인하기 위한 측정이다.

  python -m eval.audit_sockets --output result.json
  python -m eval.audit_sockets --llm-url http://127.0.0.1:1234/v1 --llm-model <모델> --output result.json

uvloop의 연결은 파이썬 감사 훅에 보이지 않으므로 asyncio 루프로 실행한다.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import httpx

from eval.dataset import ITEMS

_CHILD_FLAG = "--audited-backend"
_PORT = "18765"
_TOKEN = "audit-token"
_API = f"http://127.0.0.1:{_PORT}"
_HEADERS = {"X-Clasp-Token": _TOKEN}


def _run_audited_backend():
    log = open(os.environ["AUDIT_LOG"], "a", buffering=1, encoding="utf-8")

    def hook(event, args):
        if event == "socket.connect":
            log.write(json.dumps({"event": event, "target": str(args[1])}) + "\n")
        elif event == "socket.getaddrinfo":
            log.write(json.dumps({"event": event, "target": str(args[0])}) + "\n")

    sys.addaudithook(hook)
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=int(_PORT), log_level="warning", loop="asyncio")


def _wait_until_ready():
    for _ in range(120):
        try:
            if httpx.get(f"{_API}/health", headers=_HEADERS, timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("backend did not start")


def _scan(folder: str) -> dict:
    start = httpx.post(f"{_API}/scan/start", json={"folder_path": folder}, headers=_HEADERS, timeout=30)
    scan_id = start.json()["data"]["scan_id"]
    with httpx.stream(
        "GET", f"{_API}/scan/progress", params={"scan_id": scan_id}, headers=_HEADERS, timeout=None,
    ) as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:])
                if event["stage"] in (7, -1):
                    return event
    raise RuntimeError("scan stream ended early")


def _summarize(log_path: str) -> dict:
    counts: dict[str, int] = {}
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            key = f"{entry['event']} {entry['target']}"
            counts[key] = counts.get(key, 0) + 1
    return counts


def main():
    # eval.run replaces HOME on import, so the audited backend must not import it
    from eval.run import WRITERS

    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-url", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    home = tempfile.mkdtemp(prefix="clasp-audit-")
    audit_log = os.path.join(home, "audit.jsonl")
    open(audit_log, "w").close()
    env = {
        **os.environ,
        "HOME": home,
        "USERPROFILE": home,
        "HF_HOME": os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface")),
        "AUDIT_LOG": audit_log,
        "CLASP_API_TOKEN": _TOKEN,
    }
    process = subprocess.Popen(
        [sys.executable, "-W", "ignore", "-m", "eval.audit_sockets", _CHILD_FLAG],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_until_ready()
        if args.llm_url:
            httpx.post(f"{_API}/settings/local-llm", headers=_HEADERS, json={
                "enabled": True, "base_url": args.llm_url, "model": args.llm_model,
            }).raise_for_status()
        folder = os.path.join(home, "samples")
        os.makedirs(folder)
        for item in ITEMS:
            WRITERS[item.kind](os.path.join(folder, item.name), item.content)
        event = _scan(folder)
    finally:
        process.terminate()
        process.wait(timeout=15)

    result = {
        "files": len(ITEMS),
        "llm_model": args.llm_model,
        "scan_stage": event["stage"],
        "connections": _summarize(audit_log),
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    if _CHILD_FLAG in sys.argv:
        _run_audited_backend()
    else:
        main()
