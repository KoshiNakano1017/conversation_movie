import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { SubtitleSegment } from "../types/video-data";

interface SubtitleOverlayProps {
  subtitles: SubtitleSegment[];
  fps: number;
}

/** 現在フレームに対応する字幕を画面下部に表示するコンポーネント */
export const SubtitleOverlay: React.FC<SubtitleOverlayProps> = ({
  subtitles,
  fps,
}) => {
  const frame = useCurrentFrame();
  const currentSeconds = frame / fps;

  // 現在時刻に対応する字幕セグメントを取得
  const activeSegment = subtitles.find(
    (seg) =>
      currentSeconds >= seg.start_seconds && currentSeconds < seg.end_seconds
  );

  if (!activeSegment) return null;

  // セグメント開始からのフェードイン
  const segmentStartFrame = activeSegment.start_seconds * fps;
  const fadeIn = interpolate(
    frame - segmentStartFrame,
    [0, 6],
    [0, 1],
    { extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        position: "absolute",
        bottom: 60,
        left: 60,
        right: 60,
        opacity: fadeIn,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 6,
      }}
    >
      {/* 話者ラベル */}
      {activeSegment.speaker && (
        <div
          style={{
            backgroundColor: "rgba(99,102,241,0.85)",
            color: "#fff",
            paddingLeft: 14,
            paddingRight: 14,
            paddingTop: 4,
            paddingBottom: 4,
            borderRadius: 12,
            fontSize: 22,
            fontWeight: 600,
            alignSelf: "flex-start",
          }}
        >
          {activeSegment.speaker}
        </div>
      )}

      {/* 字幕テキスト */}
      <div
        style={{
          backgroundColor: "rgba(0,0,0,0.72)",
          color: "#fff",
          paddingLeft: 24,
          paddingRight: 24,
          paddingTop: 12,
          paddingBottom: 12,
          borderRadius: 12,
          fontSize: 34,
          fontWeight: 500,
          lineHeight: 1.5,
          textAlign: "center",
          maxWidth: "100%",
          wordBreak: "break-all",
        }}
      >
        {activeSegment.text}
      </div>
    </div>
  );
};
