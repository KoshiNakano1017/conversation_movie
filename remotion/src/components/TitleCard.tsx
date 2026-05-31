import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface TitleCardProps {
  title: string;
  themes: string[];
}

/** 動画冒頭に表示するタイトルカード（最初の90フレーム = 3秒） */
export const TitleCard: React.FC<TitleCardProps> = ({ title, themes }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 200 },
    durationInFrames: 25,
  });

  const tagsSpring = spring({
    frame: frame - 15,
    fps,
    config: { damping: 14, stiffness: 200 },
    durationInFrames: 25,
  });

  const titleY = interpolate(titleSpring, [0, 1], [40, 0]);
  const tagsY = interpolate(tagsSpring, [0, 1], [30, 0]);

  // 90フレーム以降はフェードアウト
  const fadeOut = interpolate(frame, [75, 90], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 24,
        opacity: fadeOut,
        padding: "0 80px",
      }}
    >
      {/* サービスロゴ */}
      <div
        style={{
          color: "rgba(255,255,255,0.7)",
          fontSize: 24,
          fontWeight: 500,
          letterSpacing: "0.15em",
          transform: `translateY(${titleY}px)`,
        }}
      >
        🎬 ConversationMovie
      </div>

      {/* 会議タイトル */}
      <div
        style={{
          color: "#fff",
          fontSize: 56,
          fontWeight: 800,
          textAlign: "center",
          lineHeight: 1.3,
          transform: `translateY(${titleY}px)`,
          textShadow: "0 2px 20px rgba(0,0,0,0.3)",
        }}
      >
        {title}
      </div>

      {/* テーマタグ */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          justifyContent: "center",
          transform: `translateY(${tagsY}px)`,
        }}
      >
        {themes.slice(0, 4).map((theme) => (
          <div
            key={theme}
            style={{
              backgroundColor: "rgba(255,255,255,0.2)",
              border: "1.5px solid rgba(255,255,255,0.4)",
              color: "#fff",
              fontSize: 22,
              paddingLeft: 16,
              paddingRight: 16,
              paddingTop: 6,
              paddingBottom: 6,
              borderRadius: 24,
              backdropFilter: "blur(8px)",
            }}
          >
            #{theme}
          </div>
        ))}
      </div>
    </div>
  );
};
