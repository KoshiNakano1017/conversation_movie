import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { CHARACTER_COLOR_MAP, CHARACTER_IMAGE_MAP } from "../types/video-data";

interface AvatarProps {
  characterName: string;
  /** この Avatar が登場するフレーム（slide-inアニメーションの起点） */
  appearFrame: number;
  /** 話しているかどうか（口パクアニメーションを制御） */
  isTalking: boolean;
  position: "left" | "right" | "center";
}

/** アバターキャラクターを表示するコンポーネント */
export const Avatar: React.FC<AvatarProps> = ({
  characterName,
  appearFrame,
  isTalking,
  position,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const imageSrc = CHARACTER_IMAGE_MAP[characterName] ?? "/avatars/hakase/default.png";
  const color = CHARACTER_COLOR_MAP[characterName] ?? "#6366f1";

  // ── 登場アニメーション（スプリング物理でバウンスイン） ──
  const slideProgress = spring({
    frame: frame - appearFrame,
    fps,
    config: { damping: 12, stiffness: 180, mass: 0.8 },
    durationInFrames: 30,
  });

  const translateY = interpolate(slideProgress, [0, 1], [120, 0]);
  const opacity = interpolate(slideProgress, [0, 0.3], [0, 1], {
    extrapolateRight: "clamp",
  });

  // ── 話し中の上下ゆれアニメーション ──
  const talkBounce = isTalking
    ? Math.sin((frame / fps) * Math.PI * 4) * 6
    : 0;

  // ── 位置ごとの水平オフセット ──
  const horizontalOffset = {
    left: "8%",
    right: "auto",
    center: "50%",
  }[position];
  const rightOffset = position === "right" ? "8%" : "auto";
  const transform =
    position === "center"
      ? `translateX(-50%) translateY(${translateY + talkBounce}px)`
      : `translateY(${translateY + talkBounce}px)`;

  // 画像がない環境でも可愛く見えるよう、デフォルメ顔をコード描画する
  const baseHueMap: Record<string, string> = {
    ハカセ: "#6ee7ff",
    ツッコミちゃん: "#ff90c2",
    まとめロボ: "#8ef5cc",
  };
  const baseColor = baseHueMap[characterName] ?? "#b8c0ff";
  const cheekColor = characterName === "ツッコミちゃん" ? "#ff6f9f" : "#ff9aa2";
  const antennaColor = characterName === "まとめロボ" ? "#4ade80" : "#f59e0b";

  const isBlinking = frame % (fps * 3) < 4;
  const mouthOpen = isTalking
    ? 10 + Math.sin((frame / fps) * Math.PI * 8) * 6
    : 4;
  const mouthWidth = isTalking ? 34 : 26;
  const speakingGlow = isTalking ? `0 0 32px ${color}88` : `0 0 20px ${color}55`;

  return (
    <div
      style={{
        position: "absolute",
        bottom: "18%",
        left: horizontalOffset,
        right: rightOffset,
        opacity,
        transform,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
      }}
    >
      {/* アバター本体 */}
      <div
        style={{
          width: 200,
          height: 200,
          borderRadius: "50%",
          border: `5px solid ${color}`,
          overflow: "hidden",
          boxShadow: speakingGlow,
          background: `radial-gradient(circle at 35% 30%, #ffffff 0%, ${baseColor} 64%, ${color} 100%)`,
          position: "relative",
        }}
      >
        {/* 画像が存在する場合は使う。なければデフォルメ顔のみ表示 */}
        <img
          src={imageSrc}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            position: "absolute",
            inset: 0,
            opacity: 0,
          }}
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />

        {/* 耳っぽい装飾 */}
        <div
          style={{
            position: "absolute",
            top: 18,
            left: 30,
            width: 24,
            height: 24,
            borderRadius: "50%",
            backgroundColor: "#fff8",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 22,
            right: 34,
            width: 18,
            height: 18,
            borderRadius: "50%",
            backgroundColor: "#fff6",
          }}
        />

        {/* 目 */}
        <div
          style={{
            position: "absolute",
            top: 78,
            left: 58,
            width: 24,
            height: isBlinking ? 3 : 22,
            borderRadius: 20,
            backgroundColor: "#1f2937",
            transition: "height 80ms linear",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 78,
            right: 58,
            width: 24,
            height: isBlinking ? 3 : 22,
            borderRadius: 20,
            backgroundColor: "#1f2937",
            transition: "height 80ms linear",
          }}
        />

        {/* ほっぺ */}
        <div
          style={{
            position: "absolute",
            top: 108,
            left: 36,
            width: 22,
            height: 14,
            borderRadius: "50%",
            backgroundColor: `${cheekColor}99`,
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 108,
            right: 36,
            width: 22,
            height: 14,
            borderRadius: "50%",
            backgroundColor: `${cheekColor}99`,
          }}
        />

        {/* 口パク */}
        <div
          style={{
            position: "absolute",
            left: "50%",
            bottom: 44,
            transform: "translateX(-50%)",
            width: mouthWidth,
            height: mouthOpen,
            borderRadius: 999,
            backgroundColor: "#111827",
            border: "2px solid #fff8",
          }}
        />

        {/* アンテナ/アクセサリ */}
        <div
          style={{
            position: "absolute",
            top: 6,
            left: "50%",
            transform: "translateX(-50%)",
            width: 8,
            height: 24,
            borderRadius: 999,
            backgroundColor: antennaColor,
          }}
        />
        <div
          style={{
            position: "absolute",
            top: -2,
            left: "50%",
            transform: "translateX(-50%)",
            width: 16,
            height: 16,
            borderRadius: "50%",
            backgroundColor: "#fff",
            border: `3px solid ${antennaColor}`,
          }}
        />
      </div>

      {/* キャラクター名バッジ */}
      <div
        style={{
          backgroundColor: color,
          color: "#fff",
          paddingLeft: 16,
          paddingRight: 16,
          paddingTop: 6,
          paddingBottom: 6,
          borderRadius: 20,
          fontSize: 20,
          fontWeight: 700,
          letterSpacing: "0.05em",
        }}
      >
        {characterName}
      </div>
    </div>
  );
};
