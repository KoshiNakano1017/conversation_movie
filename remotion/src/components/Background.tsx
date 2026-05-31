import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

interface BackgroundProps {
  sentiment: "positive" | "negative" | "neutral";
}

/** グラデーション背景。感情スコアに応じて色相をゆっくり変化させる */
export const Background: React.FC<BackgroundProps> = ({ sentiment }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // 感情に応じたカラーパレット
  const colorSets = {
    positive: ["#6366f1", "#a855f7", "#3b82f6"],
    negative: ["#6b7280", "#4b5563", "#374151"],
    neutral: ["#6366f1", "#8b5cf6", "#06b6d4"],
  };
  const [from, via, to] = colorSets[sentiment];

  // 時間経過でゆっくり色相がシフトするアニメーション
  const hueShift = interpolate(frame, [0, durationInFrames], [0, 30]);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: `linear-gradient(135deg, ${from} 0%, ${via} 50%, ${to} 100%)`,
        filter: `hue-rotate(${hueShift}deg)`,
      }}
    >
      {/* 光のきらめきエフェクト */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse at 20% 20%, rgba(255,255,255,0.15) 0%, transparent 60%)",
        }}
      />
    </div>
  );
};
