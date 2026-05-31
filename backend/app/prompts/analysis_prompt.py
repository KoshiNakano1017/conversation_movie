# AI-GENERATED: このプロンプトはAIと協働で設計しました。
# 生成プロンプトの意図: docs/ai-prompts/gemini_analysis.md を参照
#
# 設計方針:
# - 1回のAPIコールで全分析を取得（コスト最小化）
# - JSON出力を強制してパースを安定させる
# - 日本語・英語の両方に対応（languageパラメータで制御）

CONVERSATION_ANALYSIS_PROMPT = """\
あなたは会議・対話の分析の専門家です。
以下のトランスクリプトを読み、指定されたJSON形式で分析結果を出力してください。

## 言語
分析言語: {language}
（summaryやthemesなどのテキストはすべてこの言語で出力すること）

## トランスクリプト
---
{transcript}
---

## 出力形式（JSON のみ。説明文は一切不要）

```json
{{
  "summary_short": "3行以内の要約。会議の核心を端的に",
  "summary_medium": "200〜400文字の段落形式の要約。文脈・経緯も含む",
  "summary_detailed": {{
    "overview": "会議全体の概要",
    "key_decisions": ["決定事項1", "決定事項2"],
    "action_items": [
      {{"who": "担当者名", "what": "タスク内容", "when": "期限（不明なら空文字）"}}
    ],
    "next_steps": ["次のステップ1", "次のステップ2"]
  }},
  "themes": ["メインテーマ1", "サブテーマ2"],
  "keywords": ["キーワード1", "キーワード2", "キーワード3"],
  "quotes": [
    {{
      "speaker": "話者名（不明なら空文字）",
      "text": "印象的な発言の原文",
      "reason": "なぜ名言として選んだか（1行）"
    }}
  ],
  "overall_sentiment": "positive / negative / neutral のいずれか",
  "suggested_title": "YouTube動画タイトル（40文字以内、魅力的に）",
  "suggested_description": "YouTube動画説明文（200文字以内）",
  "suggested_tags": ["タグ1", "タグ2", "タグ3", "タグ4", "タグ5"]
}}
```

## ルール
- quotesは最大5件まで
- themesは最大5件まで
- keywordsは最大10件まで
- suggested_tagsは5〜10件
- overall_sentimentは必ず "positive" / "negative" / "neutral" のどれか
- コードブロック(```)を除いた純粋なJSONのみ返すこと
"""

AVATAR_SCRIPT_PROMPT = """\
あなたは動画のナレーター兼MCです。
以下の会議分析結果をもとに、{character_name}というキャラクターのセリフを生成してください。

## キャラクター設定
名前: {character_name}
性格・口調: {personality}

## 会議分析結果
タイトル: {title}
要約: {summary_short}
テーマ: {themes}
名言: {quotes}
アクションアイテム: {action_items}

## セリフ要件
- セクション: {section}（intro / summary / quote / outro のいずれか）
- 目安の長さ: {target_chars}文字前後
- 視聴者は会議に参加していない第三者
- キャラクターの口調・個性を必ず出す
- 専門用語は噛み砕いて説明する
- 改行は使わず1段落のテキストで返す

## セクション別の内容方針
- intro: 会議のテーマ紹介・視聴者の興味を引く導入
- summary: 会議の要点・決定事項をわかりやすく解説
- quote: 名言を紹介しその意味・背景を解説
- outro: まとめ・行動を促すメッセージ

セリフのテキストのみ返すこと（説明文・記号は不要）。
"""
