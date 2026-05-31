import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { MeetingAvatar } from "../components/MeetingAvatar";
import { SpeechBubble } from "../components/SpeechBubble";
import { SubtitleOverlay } from "../components/SubtitleOverlay";
import { SPEAKER_COLORS, VideoData } from "../types/video-data";

/** 会議室スタイルの動画コンポジション */
export const MeetingVideo: React.FC<VideoData> = (props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentSeconds = frame / fps;

  const speakers = props.speakers ?? [];
  const turns = props.speaker_turns ?? [];

  // 現在アクティブな発言ターン
  const activeTurn = turns.find(
    (t) => currentSeconds >= t.start_seconds && currentSeconds < t.end_seconds
  ) ?? null;
  const activeSpeaker = activeTurn?.speaker ?? null;

  // タイトルカードのフェードアウト（最初の3秒）
  const TITLE_SEC = 3;
  const titleOpacity = interpolate(currentSeconds, [TITLE_SEC - 0.5, TITLE_SEC], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const contentOpacity = interpolate(currentSeconds, [TITLE_SEC - 0.3, TITLE_SEC + 0.3], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // 背景グラデーション（センチメントに応じて色調が変化）
  const bgColors: Record<string, string> = {
    positive: "linear-gradient(135deg, #1a1a2e 0%, #16213e 40%, #0f3460 100%)",
    negative: "linear-gradient(135deg, #1a1a2e 0%, #2d1515 40%, #4a1f1f 100%)",
    neutral:  "linear-gradient(135deg, #1a1a2e 0%, #1e2640 40%, #252d40 100%)",
  };
  const bg = bgColors[props.overall_sentiment] ?? bgColors.neutral;

  // 参加者を最大6人に制限（レイアウト上）
  const MAX_SPEAKERS = 6;
  const displaySpeakers = speakers.slice(0, MAX_SPEAKERS);

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        position: "relative",
        overflow: "hidden",
        background: bg,
        fontFamily: "'Noto Sans JP', 'Hiragino Sans', sans-serif",
      }}
    >
      {/* ── 背景：会議室っぽいグリッド模様 ── */}
      <svg
        style={{ position: "absolute", inset: 0, opacity: 0.06 }}
        width={1920}
        height={1080}
        viewBox="0 0 1920 1080"
      >
        {/* 横線 */}
        {Array.from({ length: 12 }).map((_, i) => (
          <line key={`h${i}`} x1={0} y1={(i + 1) * 90} x2={1920} y2={(i + 1) * 90} stroke="#fff" strokeWidth={1} />
        ))}
        {/* 縦線 */}
        {Array.from({ length: 20 }).map((_, i) => (
          <line key={`v${i}`} x1={(i + 1) * 96} y1={0} x2={(i + 1) * 96} y2={1080} stroke="#fff" strokeWidth={1} />
        ))}
      </svg>

      {/* ── タイトルカード（最初の3秒） ── */}
      {titleOpacity > 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            opacity: titleOpacity,
            background: "rgba(0,0,0,0.3)",
          }}
        >
          <div
            style={{
              fontSize: 72,
              fontWeight: 900,
              color: "#fff",
              textAlign: "center",
              textShadow: "0 4px 20px rgba(0,0,0,0.5)",
              maxWidth: "80%",
              lineHeight: 1.3,
            }}
          >
            {props.title}
          </div>
          {props.themes.length > 0 && (
            <div style={{ display: "flex", gap: 16, marginTop: 32, flexWrap: "wrap", justifyContent: "center" }}>
              {props.themes.map((theme, i) => (
                <div
                  key={i}
                  style={{
                    backgroundColor: `${SPEAKER_COLORS[i % SPEAKER_COLORS.length]}cc`,
                    color: "#fff",
                    padding: "8px 20px",
                    borderRadius: 40,
                    fontSize: 28,
                    fontWeight: 600,
                  }}
                >
                  {theme}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── メインコンテンツ ── */}
      <div style={{ position: "absolute", inset: 0, opacity: contentOpacity }}>

        {/* ヘッダーバー */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 72,
            backgroundColor: "rgba(0,0,0,0.55)",
            backdropFilter: "blur(8px)",
            display: "flex",
            alignItems: "center",
            paddingLeft: 48,
            paddingRight: 48,
            justifyContent: "space-between",
            borderBottom: "1px solid rgba(255,255,255,0.15)",
          }}
        >
          <div style={{ color: "#fff", fontSize: 28, fontWeight: 700 }}>{props.title}</div>
          <div
            style={{
              backgroundColor: `${SPEAKER_COLORS[0]}cc`,
              color: "#fff",
              padding: "6px 18px",
              borderRadius: 20,
              fontSize: 22,
              fontWeight: 600,
            }}
          >
            🎙 会議録
          </div>
        </div>

        {/* 参加者アバターグリッド */}
        <div
          style={{
            position: "absolute",
            top: 100,
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            alignItems: "flex-end",
            gap: displaySpeakers.length > 4 ? 48 : 80,
            paddingLeft: 48,
            paddingRight: 48,
          }}
        >
          {displaySpeakers.map((spk, i) => {
            // そのスピーカーが最初に登場するターン
            const firstTurn = turns.find((t) => t.speaker === spk);
            const appearFrame = firstTurn
              ? Math.max(0, firstTurn.start_seconds * fps - 5)
              : TITLE_SEC * fps;

            return (
              <MeetingAvatar
                key={spk}
                speaker={spk}
                speakerIndex={i}
                isActive={activeSpeaker === spk}
                appearFrame={appearFrame}
              />
            );
          })}
        </div>

        {/* アクティブ発言バブル */}
        {turns.map((turn, i) => {
          const spkIdx = speakers.indexOf(turn.speaker);
          return (
            <SpeechBubble
              key={i}
              turn={turn}
              speakerIndex={spkIdx >= 0 ? spkIdx : i}
              fps={fps}
            />
          );
        })}

        {/* 字幕オーバーレイ */}
        <SubtitleOverlay subtitles={props.subtitles} fps={fps} />
      </div>
    </div>
  );
};
