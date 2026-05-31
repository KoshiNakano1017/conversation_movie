import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { AvatarScript } from "../types/video-data";
import { CHARACTER_COLOR_MAP } from "../types/video-data";

interface ScriptDisplayProps {
  script: AvatarScript;
  fps: number;
}

/** アバターのセリフを吹き出し風に表示するコンポーネント */
export const ScriptDisplay: React.FC<ScriptDisplayProps> = ({
  script,
  fps,
}) => {
  const frame = useCurrentFrame();
  const currentSeconds = frame / fps;
  const scriptStartFrame = script.start_seconds * fps;
  const scriptEndFrame = (script.start_seconds + script.duration_seconds) * fps;

  const isActive =
    currentSeconds >= script.start_seconds &&
    currentSeconds < script.start_seconds + script.duration_seconds;

  const fadeIn = interpolate(frame - scriptStartFrame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });

  const fadeOut = interpolate(
    frame,
    [scriptEndFrame - 10, scriptEndFrame],
    [1, 0],
    { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
  );

  const opacity = isActive ? Math.min(fadeIn, fadeOut) : 0;

  const color = CHARACTER_COLOR_MAP[script.character_name] ?? "#6366f1";

  if (opacity === 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        top: "12%",
        left: "50%",
        transform: "translateX(-50%)",
        width: "74%",
        opacity,
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(255,255,255,0.95)",
          border: `3px solid ${color}`,
          borderRadius: 20,
          padding: "24px 32px",
          fontSize: 32,
          lineHeight: 1.7,
          color: "#1e293b",
          textAlign: "center",
          boxShadow: `0 8px 32px ${color}40`,
          position: "relative",
        }}
      >
        {/* セクションバッジ */}
        <div
          style={{
            position: "absolute",
            top: -16,
            left: 24,
            backgroundColor: color,
            color: "#fff",
            fontSize: 18,
            fontWeight: 700,
            paddingLeft: 12,
            paddingRight: 12,
            paddingTop: 4,
            paddingBottom: 4,
            borderRadius: 8,
          }}
        >
          {sectionLabel(script.section)}
        </div>

        {script.script_text}
      </div>
    </div>
  );
};

function sectionLabel(section: string): string {
  const labels: Record<string, string> = {
    intro: "📢 導入",
    summary: "📋 まとめ",
    quote: "💬 名言",
    outro: "🎯 ポイント",
  };
  return labels[section] ?? section;
}
