import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { SPEAKER_COLORS } from "../types/video-data";

interface MeetingAvatarProps {
  speaker: string;
  speakerIndex: number;
  isActive: boolean;
  /** このアバターが最初に登場するフレーム */
  appearFrame: number;
}

/** 会議参加者1人を丸いアバターで表示するコンポーネント */
export const MeetingAvatar: React.FC<MeetingAvatarProps> = ({
  speaker,
  speakerIndex,
  isActive,
  appearFrame,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const color = SPEAKER_COLORS[speakerIndex % SPEAKER_COLORS.length];

  // 登場アニメーション
  const slideProgress = spring({
    frame: frame - appearFrame,
    fps,
    config: { damping: 14, stiffness: 200, mass: 0.7 },
    durationInFrames: 20,
  });
  const opacity = interpolate(slideProgress, [0, 1], [0, 1], { extrapolateRight: "clamp" });
  const scale = interpolate(slideProgress, [0, 1], [0.5, 1], { extrapolateRight: "clamp" });

  // 話し中のボブアニメ
  const talkBob = isActive ? Math.sin((frame / fps) * Math.PI * 5) * 8 : 0;
  // アクティブ時の拡大
  const activeScale = isActive
    ? 1 + interpolate(Math.sin((frame / fps) * Math.PI * 3), [-1, 1], [0, 0.05])
    : 1;

  // まばたき
  const isBlinking = frame % (fps * 3) < 3;
  // 口パク
  const mouthH = isActive ? 8 + Math.sin((frame / fps) * Math.PI * 8) * 5 : 3;
  const mouthW = isActive ? 28 : 20;

  // 参加者イニシャル
  const initial = speaker.charAt(0);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 10,
        opacity,
        transform: `scale(${scale * activeScale}) translateY(${talkBob}px)`,
        transition: "transform 0.05s",
      }}
    >
      {/* アバター本体 */}
      <div
        style={{
          width: isActive ? 170 : 140,
          height: isActive ? 170 : 140,
          borderRadius: "50%",
          background: `radial-gradient(circle at 35% 30%, #fff 0%, ${color}99 55%, ${color} 100%)`,
          border: `${isActive ? 6 : 3}px solid ${color}`,
          boxShadow: isActive
            ? `0 0 40px ${color}cc, 0 0 80px ${color}44`
            : `0 4px 20px ${color}44`,
          position: "relative",
          overflow: "hidden",
          transition: "width 0.15s, height 0.15s, border-width 0.15s",
        }}
      >
        {/* 目 */}
        <div style={{ position: "absolute", top: "36%", left: "28%", width: 20, height: isBlinking && isActive ? 2 : 18, borderRadius: 20, backgroundColor: "#1f2937" }} />
        <div style={{ position: "absolute", top: "36%", right: "28%", width: 20, height: isBlinking && isActive ? 2 : 18, borderRadius: 20, backgroundColor: "#1f2937" }} />
        {/* ほっぺ */}
        <div style={{ position: "absolute", top: "56%", left: "18%", width: 20, height: 12, borderRadius: "50%", backgroundColor: "#ff9aa288" }} />
        <div style={{ position: "absolute", top: "56%", right: "18%", width: 20, height: 12, borderRadius: "50%", backgroundColor: "#ff9aa288" }} />
        {/* 口パク */}
        <div style={{ position: "absolute", bottom: "24%", left: "50%", transform: "translateX(-50%)", width: mouthW, height: mouthH, borderRadius: 999, backgroundColor: "#111827", border: "1.5px solid #fff6" }} />
        {/* 頭上アクセント */}
        <div style={{ position: "absolute", top: 4, left: "50%", transform: "translateX(-50%)", width: 6, height: 20, borderRadius: 999, backgroundColor: `${color}cc` }} />
        <div style={{ position: "absolute", top: -2, left: "50%", transform: "translateX(-50%)", width: 14, height: 14, borderRadius: "50%", backgroundColor: "#fff", border: `3px solid ${color}` }} />
      </div>

      {/* 名前バッジ */}
      <div
        style={{
          backgroundColor: isActive ? color : `${color}88`,
          color: "#fff",
          paddingLeft: 16,
          paddingRight: 16,
          paddingTop: 6,
          paddingBottom: 6,
          borderRadius: 24,
          fontSize: isActive ? 26 : 22,
          fontWeight: 700,
          letterSpacing: "0.04em",
          boxShadow: isActive ? `0 4px 16px ${color}88` : "none",
          transition: "font-size 0.15s, background-color 0.15s",
        }}
      >
        {speaker}
      </div>
    </div>
  );
};
