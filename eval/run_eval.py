"""评测脚本：自动运行 evalset.json 中的场景，输出评分报告（JSON + Markdown）。

用法：
  python eval/run_eval.py              # 需已启动后端（http://localhost:8000）
  python eval/run_eval.py --no-serve   # 用 TestClient 内存跑（CI 用，无需启动服务）
  python eval/run_eval.py --serve --port 8000  # 用真实 HTTP 调用

评分维度：
  - format_ok          : 战报结构是否合规（含 final_choice/reason/score 等字段）
  - final_choice_valid : final_choice 是否有效（非空，若 menu_mode 则在候选中）
  - score_ok           : score 是否在 0~10 区间
  - time_ms            : 响应耗时
  - llm_calls          : LLM 调用次数（N 轮 × 2 大厨 + 1 战报）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# 允许从仓库根目录导入 src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EVALSET = Path(__file__).parent / "evalset.json"
SAMPLE_MENU = Path(__file__).parent / "sample_menu.json"


def _load_menu_items() -> list[dict]:
    with open(SAMPLE_MENU, encoding="utf-8") as f:
        return json.load(f)["items"]


def _run_with_testclient(case: dict, menu_items: list[dict]) -> dict:
    """用 TestClient 内存运行单个场景（CI 模式）。"""
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["LLM_PROVIDER"] = "mock"

    from fastapi.testclient import TestClient
    from src.main import app, limiter

    # 每个场景重置限频器，避免跨场景累积触发 429
    limiter.reset()

    start = time.time()
    with TestClient(app) as client:
        # 若 menu_mode，先导入菜单
        if case["expected"].get("menu_mode"):
            client.post("/api/menus/import", json={"items": menu_items})

        resp = client.post("/api/debate/start", json=case["input"])
        elapsed_ms = (time.time() - start) * 1000

        if resp.status_code != 201:
            return {
                "status": resp.status_code,
                "time_ms": round(elapsed_ms, 1),
                "error": resp.text[:200],
            }

        data = resp.json()
        rec = data.get("recommendation") or {}

        # LLM 调用次数估算：rounds 条发言 + 1 战报
        rounds = data.get("rounds", [])
        llm_calls = len(rounds) + 1

        return {
            "status": resp.status_code,
            "time_ms": round(elapsed_ms, 1),
            "llm_calls": llm_calls,
            "final_choice": rec.get("final_choice", ""),
            "score": rec.get("score"),
            "price": rec.get("price"),
            "rounds": len(rounds),
        }


def _run_with_http(case: dict, menu_items: list[dict], base_url: str) -> dict:
    """用真实 HTTP 调用运行单个场景。"""
    import httpx

    start = time.time()
    with httpx.Client(base_url=base_url, timeout=120.0) as client:
        if case["expected"].get("menu_mode"):
            client.post("/api/menus/import", json={"items": menu_items})
        resp = client.post("/api/debate/start", json=case["input"])
        elapsed_ms = (time.time() - start) * 1000

        if resp.status_code != 201:
            return {
                "status": resp.status_code,
                "time_ms": round(elapsed_ms, 1),
                "error": resp.text[:200],
            }

        data = resp.json()
        rec = data.get("recommendation") or {}
        rounds = data.get("rounds", [])
        return {
            "status": resp.status_code,
            "time_ms": round(elapsed_ms, 1),
            "llm_calls": len(rounds) + 1,
            "final_choice": rec.get("final_choice", ""),
            "score": rec.get("score"),
            "price": rec.get("price"),
            "rounds": len(rounds),
        }


def _score(result: dict, case: dict, menu_items: list[dict]) -> dict:
    """对单个结果评分，返回带 verdict 的条目。"""
    expected = case["expected"]
    verdicts = []

    # 1. 格式合规
    format_ok = result.get("status") == 201 and "final_choice" in result
    verdicts.append(("format_ok", format_ok))

    # 2. final_choice 有效性
    fc = result.get("final_choice", "")
    final_valid = bool(fc)
    if final_valid and expected.get("in_candidates"):
        names = [m["name"] for m in menu_items]
        final_valid = fc in names or any(fc in n or n in fc for n in names)
    verdicts.append(("final_choice_valid", final_valid))

    # 3. score 范围
    score = result.get("score")
    lo, hi = expected.get("score_range", [0, 10])
    score_ok = isinstance(score, (int, float)) and lo <= score <= hi
    verdicts.append(("score_ok", score_ok))

    # 4. 价格存在性（若要求）
    if expected.get("has_price"):
        verdicts.append(("has_price", result.get("price") is not None))

    # 5. 响应时间合理（< 30s，Mock 下通常 < 1s）
    time_ok = result.get("time_ms", 99999) < 30000
    verdicts.append(("time_ok", time_ok))

    all_pass = all(v for _, v in verdicts)
    return {
        "id": case["id"],
        "input": case["input"],
        "result": result,
        "verdicts": dict(verdicts),
        "passed": all_pass,
    }


def _render_markdown(scored: list[dict], summary: dict) -> str:
    lines = ["# 评测报告 — Cyber Foodie Agent", ""]
    lines.append(f"- 场景总数：{summary['total']}")
    lines.append(f"- 通过：{summary['passed']}")
    lines.append(f"- 失败：{summary['failed']}")
    lines.append(f"- 通过率：{summary['pass_rate']:.1%}")
    lines.append(f"- 平均响应时间：{summary['avg_time_ms']:.1f} ms")
    lines.append(f"- 平均 LLM 调用次数：{summary['avg_llm_calls']:.1f}")
    lines.append("")
    lines.append("| 场景 | 状态 | 响应时间 | LLM调用 | final_choice | score |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for s in scored:
        status = "PASS" if s["passed"] else "FAIL"
        r = s["result"]
        lines.append(
            f"| {s['id']} | {status} | {r.get('time_ms', '—')}ms | {r.get('llm_calls', '—')} | "
            f"{r.get('final_choice', '—')} | {r.get('score', '—')} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="运行评测")
    parser.add_argument("--no-serve", action="store_true", help="用 TestClient 内存运行")
    parser.add_argument("--base-url", default="http://localhost:8000", help="后端地址")
    parser.add_argument("--output-json", default="eval/report.json", help="JSON 报告输出路径")
    parser.add_argument("--output-md", default="eval/report.md", help="Markdown 报告输出路径")
    args = parser.parse_args()

    with open(EVALSET, encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    menu_items = _load_menu_items()

    scored = []
    total_time = 0.0
    total_calls = 0
    for case in cases:
        if args.no_serve:
            result = _run_with_testclient(case, menu_items)
        else:
            result = _run_with_http(case, menu_items, args.base_url)

        s = _score(result, case, menu_items)
        scored.append(s)
        total_time += result.get("time_ms", 0)
        total_calls += result.get("llm_calls", 0)

    passed = sum(1 for s in scored if s["passed"])
    total = len(scored)
    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total else 0,
        "avg_time_ms": round(total_time / total, 1) if total else 0,
        "avg_llm_calls": round(total_calls / total, 1) if total else 0,
    }

    report = {"summary": summary, "cases": scored}
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(args.output_md, "w", encoding="utf-8") as f:
        f.write(_render_markdown(scored, summary))

    print(_render_markdown(scored, summary))
    # 全部通过返回 0，否则返回 1（供 CI 判定）
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
