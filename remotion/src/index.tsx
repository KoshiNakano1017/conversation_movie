import React from "react";
import { Composition, registerRoot } from "remotion";
import { AvatarVideo } from "./compositions/AvatarVideo";
import { MeetingVideo } from "./compositions/MeetingVideo";
import { VideoData } from "./types/video-data";

// ── デフォルトprops（Remotion Studio / テスト用プレビューデータ） ──
const defaultVideoData: VideoData = {
  job_id: "preview",
  title: "戦略思考とデザイン思考MTG",
  duration_frames: 900,
  fps: 30,
  overall_sentiment: "positive",
  themes: ["戦略思考", "デザイン思考", "仮説検証"],
  quotes: [
    { speaker: "森本", text: "戦略の本質は「選択」です。", reason: "核心をつく発言" },
  ],
  summary_short: "戦略思考とデザイン思考の違いと活かし方を整理しました。",
  subtitles: [
    { index: 1, start_seconds: 4, end_seconds: 8, speaker: "田島", text: "本日は戦略思考とデザイン思考の違いを整理します。" },
    { index: 2, start_seconds: 8, end_seconds: 14, speaker: "森本", text: "戦略思考は限られたリソースの中でどこで勝つかを選ぶ思考です。" },
  ],
  avatar_scripts: [],
  speaker_turns: [
    { speaker: "田島", text: "本日は戦略思考とデザイン思考の違いを整理します。", start_seconds: 3, end_seconds: 9 },
    { speaker: "森本", text: "戦略思考は限られたリソースの中でどこで勝つかを選ぶ思考です。", start_seconds: 9.4, end_seconds: 17 },
    { speaker: "佐藤", text: "デザイン思考はユーザーの文脈に入り込んで課題を深掘りします。", start_seconds: 17.4, end_seconds: 25 },
    { speaker: "木村", text: "戦略が何をやらないかを決め、デザイン思考がどう作るかを具体化します。", start_seconds: 25.4, end_seconds: 34 },
  ],
  speakers: ["田島", "森本", "佐藤", "木村"],
};

/** calculateMetadata 共通関数 */
const calcMeta = ({ props }: { props: Record<string, unknown> }) => {
  const p = props as unknown as VideoData;
  return {
    durationInFrames: p.duration_frames ?? defaultVideoData.duration_frames,
    fps: p.fps ?? defaultVideoData.fps,
  };
};

registerRoot(() => (
  <>
    {/* 会議室スタイル（新形式） */}
    <Composition
      id="MeetingVideo"
      component={MeetingVideo as unknown as React.FC<Record<string, unknown>>}
      durationInFrames={defaultVideoData.duration_frames}
      fps={defaultVideoData.fps}
      width={1920}
      height={1080}
      defaultProps={defaultVideoData}
      calculateMetadata={calcMeta}
    />

    {/* 旧アバタースタイル（後方互換） */}
    <Composition
      id="AvatarVideo"
      component={AvatarVideo as unknown as React.FC<Record<string, unknown>>}
      durationInFrames={defaultVideoData.duration_frames}
      fps={defaultVideoData.fps}
      width={1920}
      height={1080}
      defaultProps={defaultVideoData}
      calculateMetadata={calcMeta}
    />
  </>
));
