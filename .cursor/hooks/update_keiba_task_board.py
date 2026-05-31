#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "keiba" / "docs"
LOGS_DIR = DOCS_DIR / "Logs"
TASK_SOURCE_PATH = DOCS_DIR / "13_タスク管理表.tasks.json"
TASK_BOARD_PATH = DOCS_DIR / "13_タスク管理表.md"

PHASE_LABELS = {
    "contract_before": "契約前必須",
    "contract_after": "契約後すぐ",
    "later": "後回し",
}

PHASE_ORDER = ["contract_before", "contract_after", "later"]

TRACKED_PATHS = [
    ROOT / "crossfactor_meeting_doc.md",
    DOCS_DIR / "10_要件定義書.md",
    DOCS_DIR / "11_特徴量設計.md",
    DOCS_DIR / "12_抽出スクリプト設計書.md",
]


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_manual_tasks() -> list[dict]:
    return json.loads(read_text(TASK_SOURCE_PATH))


def tracked_sources() -> list[Path]:
    paths = [path for path in TRACKED_PATHS if path.exists()]
    paths.extend(sorted(LOGS_DIR.glob("*.md")))
    return paths


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_separator_row(line: str) -> bool:
    return bool(re.fullmatch(r"\|\s*[:-]+(?:\s*\|\s*[:-]+)+\s*\|?", line.strip()))


def parse_markdown_tables(text: str) -> list[tuple[list[str], list[dict[str, str]]]]:
    lines = text.splitlines()
    tables: list[tuple[list[str], list[dict[str, str]]]] = []
    i = 0
    while i < len(lines) - 1:
        if lines[i].lstrip().startswith("|") and is_separator_row(lines[i + 1]):
            headers = split_row(lines[i])
            rows: list[dict[str, str]] = []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                values = split_row(lines[i])
                if len(values) < len(headers):
                    values.extend([""] * (len(headers) - len(values)))
                rows.append(dict(zip(headers, values)))
                i += 1
            tables.append((headers, rows))
            continue
        i += 1
    return tables


def extract_section_bullets(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    bullets: list[str] = []
    active = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^###\s+", stripped):
            active = stripped == heading
            continue
        if active:
            if re.match(r"^##\s+", stripped):
                break
            if stripped.startswith("- "):
                bullets.append(stripped[2:].strip())
    return bullets


def extract_auto_tasks() -> list[dict]:
    auto_tasks: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for path in tracked_sources():
        text = read_text(path)
        rel = relative(path)

        for headers, rows in parse_markdown_tables(text):
            header_set = set(headers)

            if {"アクション", "担当", "期限"}.issubset(header_set):
                for row in rows:
                    title = row.get("アクション", "").strip()
                    owner = row.get("担当", "").strip()
                    due_date = row.get("期限", "").strip()
                    if not title:
                        continue
                    key = (title, rel)
                    if key in seen:
                        continue
                    seen.add(key)
                    auto_tasks.append(
                        {
                            "title": title,
                            "owner": owner or "要確認",
                            "due_date": due_date or "-",
                            "source": rel,
                            "notes": "ソース文書から自動検知",
                        }
                    )

            if {"ドキュメント", "内容"}.issubset(header_set):
                for row in rows:
                    document = row.get("ドキュメント", "").strip()
                    content = row.get("内容", "").strip()
                    if not document or not content:
                        continue
                    title = f"{document} を更新する"
                    key = (title, rel)
                    if key in seen:
                        continue
                    seen.add(key)
                    auto_tasks.append(
                        {
                            "title": title,
                            "owner": "中野晃志",
                            "due_date": "-",
                            "source": rel,
                            "notes": content,
                        }
                    )

        if path.name == "crossfactor_meeting_doc.md":
            for heading, owner in [("### 発注者側", "D"), ("### 開発側", "中野晃志")]:
                for bullet in extract_section_bullets(text, heading):
                    key = (bullet, rel)
                    if key in seen:
                        continue
                    seen.add(key)
                    auto_tasks.append(
                        {
                            "title": bullet,
                            "owner": owner,
                            "due_date": "-",
                            "source": rel,
                            "notes": "会議メモの次回アクション",
                        }
                    )

    auto_tasks.sort(key=lambda item: (item["source"], item["title"]))
    return auto_tasks


def render_summary(tasks: list[dict]) -> str:
    lines = [
        "| 区分 | 件数 | 高優先 |",
        "|------|------|--------|",
    ]
    for phase in PHASE_ORDER:
        phase_tasks = [task for task in tasks if task["phase"] == phase]
        high_count = sum(1 for task in phase_tasks if task["priority"] == "高")
        lines.append(f"| {PHASE_LABELS[phase]} | {len(phase_tasks)} | {high_count} |")
    return "\n".join(lines)


def render_task_table(tasks: list[dict]) -> str:
    lines = [
        "| ID | 優先 | タスク | 担当 | 期限 | 状態 | ソース | 備考 |",
        "|----|------|--------|------|------|------|--------|------|",
    ]
    for task in tasks:
        lines.append(
            f"| {task['id']} | {task['priority']} | {task['title']} | {task['owner']} | "
            f"{task['due_date']} | {task['status']} | `{task['source']}` | {task['notes']} |"
        )
    return "\n".join(lines)


def render_auto_task_table(tasks: list[dict]) -> str:
    if not tasks:
        return "_自動検知されたフォローアップはありません。_"

    lines = [
        "| タスク | 担当 | 期限 | ソース | メモ |",
        "|--------|------|------|--------|------|",
    ]
    for task in tasks:
        lines.append(
            f"| {task['title']} | {task['owner']} | {task['due_date']} | "
            f"`{task['source']}` | {task['notes']} |"
        )
    return "\n".join(lines)


def render_source_table(paths: list[Path]) -> str:
    lines = [
        "| ソース | 最終更新 | 種別 |",
        "|--------|----------|------|",
    ]
    for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True):
        kind = "会議/意思決定" if "Logs" in relative(path) or path.name == "crossfactor_meeting_doc.md" else "正本"
        modified = path.stat().st_mtime_ns
        timestamp = _format_timestamp(modified)
        lines.append(f"| `{relative(path)}` | {timestamp} | {kind} |")
    return "\n".join(lines)


def _format_timestamp(timestamp_ns: int) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(timestamp_ns / 1_000_000_000).strftime("%Y-%m-%d %H:%M")


def render_markdown(tasks: list[dict], auto_tasks: list[dict], sources: list[Path]) -> str:
    lines = [
        "# タスク管理表",
        "",
        "> このファイルは `13_タスク管理表.tasks.json` と会議/意思決定資料から自動生成されます。",
        "> `crossfactor_meeting_doc.md`、`keiba/docs/Logs/*.md`、`keiba/docs/10_要件定義書.md`、`keiba/docs/11_特徴量設計.md` 等の更新時にフックで再生成されます。",
        "",
        "## 運用メモ",
        "",
        "- `契約前必須`: 契約締結までに合意・回収・整理が必要な事項",
        "- `契約後すぐ`: 契約後すぐに着手する設計/構築タスク",
        "- `後回し`: Phase 2以降や運用整備で対応する事項",
        "- `USER_指数`: 各利用ユーザーが任意に定義するカスタム指数。採用対象は利用ユーザーに合わせて決める",
        "",
        "## サマリー",
        "",
        render_summary(tasks),
    ]

    for phase in PHASE_ORDER:
        phase_tasks = [task for task in tasks if task["phase"] == phase]
        lines.extend(
            [
                "",
                f"## {PHASE_LABELS[phase]}",
                "",
                render_task_table(phase_tasks),
            ]
        )

    lines.extend(
        [
            "",
            "## 自動検知されたフォローアップ",
            "",
            render_auto_task_table(auto_tasks),
            "",
            "## 監視対象ソース",
            "",
            render_source_table(sources),
            "",
            "## 自動更新ルール",
            "",
            "1. `13_タスク管理表.tasks.json` に人手で優先度・期限・状態を管理する。",
            "2. 会議メモや意思決定ログ、要件/特徴量設計書を編集すると、フックが本ファイルを再生成する。",
            "3. ソース更新によって新しいアクションが出た場合は、`自動検知されたフォローアップ` に反映される。",
            "4. 正式に追跡するタスクは `13_タスク管理表.tasks.json` に追加して管理する。",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    tasks = load_manual_tasks()
    auto_tasks = extract_auto_tasks()
    sources = tracked_sources()
    content = render_markdown(tasks, auto_tasks, sources)

    TASK_BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    previous = TASK_BOARD_PATH.read_text(encoding="utf-8") if TASK_BOARD_PATH.exists() else ""
    if previous != content:
        TASK_BOARD_PATH.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
