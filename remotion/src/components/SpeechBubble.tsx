import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { SPEAKER_COLORS, SpeakerTurn } from "../types/video-data";

interface SpeechBubbleProps {
  turn: SpeakerTurn;
  speakerIndex: number;
  fps: number;
}

/** アクティブな発言者のセリフをバブル表示するコンポーネント */
export const SpeechBubble: React.FC<SpeechBubbleProps> = ({ turn, speakerIndex, fps }) => {
  const frame = useCurrentFrame();
  const currentSeconds = frame / fps;
  const color = SPEAKER_COLORS[speakerIndex % SPEAKER_COLORS.length];

  const startFrame = turn.start_seconds * fps;
  const endFrame = turn.end_seconds * fps;

  const fadeIn = interpolate(frame - startFrame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(frame, [endFrame - 8, endFrame], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = Math.min(fadeIn, fadeOut);

  if (opacity <= 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 160,
        left: "50%",
        transform: "translateX(-50%)",
        width: "76%",
        opacity,
      }}
    >
      {/* スピーカーラベル */}
      <div
        style={{
          display: "inline-block",
          backgroundColor: color,
          color: "#fff",
          fontSize: 24,
          fontWeight: 700,
          paddingLeft: 20,
          paddingRight: 20,
          paddingTop: 6,
          paddingBottom: 6,
          borderRadius: "12px 12px 0 0",
          marginBottom: -2,
        }}
      >
        {turn.speaker}
      </div>
      {/* バブル本体 */}
      <div
        style={{
          backgroundColor: "rgba(255, 255, 255, 0.96)",
          border: `3px solid ${color}`,
          borderRadius: "0 16px 16px 16px",
          padding: "20px 32px",
          fontSize: 34,
          lineHeight: 1.65,
          color: "#1e293b",
          boxShadow: `0 8px 40px ${color}33`,
        }}
      >
        {turn.text}
      </div>
    </div>
  );
};
