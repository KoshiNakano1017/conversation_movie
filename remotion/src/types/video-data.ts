/** Pythonバックエンドから渡される動画生成データの型定義 */

export interface SubtitleSegment {
  index: number;
  start_seconds: number;
  end_seconds: number;
  speaker: string;
  text: string;
}

export interface AvatarScript {
  character_name: string;
  section: "intro" | "summary" | "quote" | "outro";
  script_text: string;
  duration_seconds: number;
  /** 動画内の開始秒（Pythonが計算して付与） */
  start_seconds: number;
}

/** 会議参加者の1発言ターン */
export interface SpeakerTurn {
  speaker: string;
  text: string;
  start_seconds: number;
  end_seconds: number;
}

export interface Quote {
  speaker: string;
  text: string;
  reason: string;
}

export interface VideoData {
  job_id: string;
  title: string;
  /** 動画の総フレーム数 (fps=30で計算済み) */
  duration_frames: number;
  fps: number;
  subtitles: SubtitleSegment[];
  avatar_scripts: AvatarScript[];
  summary_short: string;
  themes: string[];
  quotes: Quote[];
  overall_sentiment: "positive" | "negative" | "neutral";
  /** 会議参加者の発言ターン（会議室ビュー用） */
  speaker_turns: SpeakerTurn[];
  /** 参加者一覧（登場順・重複なし） */
  speakers: string[];
}

/** 参加者ごとのカラーパレット（最大8人） */
export const SPEAKER_COLORS: string[] = [
  "#4ECDC4", // teal
  "#FF6B6B", // coral
  "#95E1D3", // mint
  "#F7DC6F", // yellow
  "#BB8FCE", // purple
  "#F0B27A", // orange
  "#7FB3D3", // blue
  "#82E0AA", // green
];

/** キャラクター名から画像パスを解決するマップ */
export const CHARACTER_IMAGE_MAP: Record<string, string> = {
  ハカセ: "/avatars/hakase/default.png",
  ツッコミちゃん: "/avatars/tsukkomi/default.png",
  まとめロボ: "/avatars/matomerobo/default.png",
};

/** キャラクター名からカラーを解決するマップ */
export const CHARACTER_COLOR_MAP: Record<string, string> = {
  ハカセ: "#4ECDC4",
  ツッコミちゃん: "#FF6B6B",
  まとめロボ: "#95E1D3",
};
