import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Avatar } from "../components/Avatar";
import { Background } from "../components/Background";
import { ScriptDisplay } from "../components/ScriptDisplay";
import { SubtitleOverlay } from "../components/SubtitleOverlay";
import { TitleCard } from "../components/TitleCard";
import { VideoData } from "../types/video-data";

/** メイン動画コンポジション（16:9 / 1920x1080） */
export const AvatarVideo: React.FC<VideoData> = (props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentSeconds = frame / fps;

  const INTRO_DURATION_SECONDS = 3; // タイトルカード表示時間

  const isInIntro = currentSeconds < INTRO_DURATION_SECONDS;

  // 現在時刻に対応するアバタースクリプトを取得
  const activeScript = props.avatar_scripts.find(
    (s) =>
      currentSeconds >= s.start_seconds &&
      currentSeconds < s.start_seconds + s.duration_seconds
  );

  // 現在アクティブなキャラクターを判定
  const activeCharacterName = activeScript?.character_name ?? null;

  // キャラクター別の配置ポジション
  const characterPositions: Record<string, "left" | "right" | "center"> = {
    ハカセ: "left",
    ツッコミちゃん: "right",
    まとめロボ: "center",
  };

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        position: "relative",
        overflow: "hidden",
        fontFamily: "'Noto Sans JP', 'Hiragino Sans', sans-serif",
      }}
    >
      {/* 背景 */}
      <Background sentiment={props.overall_sentiment} />

      {/* タイトルカード（イントロのみ） */}
      {isInIntro && (
        <TitleCard title={props.title} themes={props.themes} />
      )}

      {/* アバターキャラクター群（イントロ後に表示） */}
      {!isInIntro &&
        [...new Set(props.avatar_scripts.map((s) => s.character_name))].map(
          (name) => {
            // このキャラクターが最初に登場するフレーム
            const firstScript = props.avatar_scripts.find(
              (s) => s.character_name === name
            );
            const appearFrame = firstScript
              ? firstScript.start_seconds * fps
              : INTRO_DURATION_SECONDS * fps;

            return (
              <Avatar
                key={name}
                characterName={name}
                appearFrame={appearFrame}
                isTalking={activeCharacterName === name}
                position={characterPositions[name] ?? "center"}
              />
            );
          }
        )}

      {/* アバターのセリフ表示 */}
      {!isInIntro &&
        props.avatar_scripts.map((script, i) => (
          <ScriptDisplay key={i} script={script} fps={fps} />
        ))}

      {/* 字幕オーバーレイ（常時表示） */}
      <SubtitleOverlay subtitles={props.subtitles} fps={fps} />
    </div>
  );
};
