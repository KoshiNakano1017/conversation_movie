"""会議室スタイルの動画を新しい戦略思考トランスクリプトで生成する"""
import sys
sys.path.insert(0, ".")
import logging
logging.disable(logging.CRITICAL)
from pathlib import Path
from app.models.job import JobStatus
from app.services.job_service import update_job_status, add_job_log
from app.services.tts_service import TTSService
from app.services.video_service import VideoService
from app.services.storage_service import StorageService
from app.workers.video_worker import _fetch_required_data, _save_video_record

JOB = "65ce63c2-6167-40fc-bd30-03551002a8d9"

print("[1/5] データ取得...")
title, uid, analysis, srt, scripts, audio, speaker_turns, speakers = _fetch_required_data(JOB)
print(f"  speakers: {speakers}")
print(f"  turns: {len(speaker_turns)}")

svc = VideoService()
vd = svc.build_video_data(JOB, title, analysis, [], scripts,
                           speaker_turns=speaker_turns, speakers=speakers)
print(f"  duration_frames={vd.duration_frames}  turns={len(vd.speaker_turns)}  speakers={vd.speakers}")

job_dir = Path("C:/Users/nakano-ko/Desktop/ConversationMovie/media/video") / JOB
update_job_status(JOB, JobStatus.GENERATING_VIDEO, progress=65)

print("[2/5] Remotion (MeetingVideo) レンダリング中...")
add_job_log(JOB, "video", f"Remotionレンダリング開始（{vd.duration_frames}フレーム）")
raw = svc.render_video(vd, "meeting_full.mp4")
print(f"  レンダリング完了: {raw.name}  {raw.stat().st_size//1024}KB")
update_job_status(JOB, JobStatus.GENERATING_VIDEO, progress=85)

print("[3/5] 字幕焼き込み...")
final = svc.burn_subtitles(raw, srt) if srt else raw
print(f"  完了: {final.name}")

print("[4/5] TTS音声生成（参加者ごと）...")
tts = TTSService()
add_job_log(JOB, "video", "TTS音声生成開始（参加者ごと）")
turns_with_audio = tts.generate_for_speaker_turns(speaker_turns, speakers, job_dir)
for t in turns_with_audio:
    ap = t.get("audio_path")
    sz = Path(ap).stat().st_size if ap else 0
    print(f"  {t['speaker']}: {sz//1024}KB")

print("[5/5] 音声合成・完了...")
final = svc.mix_tts_audio(final, turns_with_audio)
print(f"  完了: {final}")

thumb = svc.extract_thumbnail(final, 4.0)
update_job_status(JOB, JobStatus.GENERATING_VIDEO, progress=92)
meta = svc.get_video_metadata(final)
st = StorageService()
_save_video_record(JOB, uid, st.get_video_url(JOB, final.name), st.get_thumbnail_url(JOB), meta)
update_job_status(JOB, JobStatus.COMPLETED, progress=100)
add_job_log(JOB, "video", "動画生成完了", details={"file_size_bytes": meta.get("file_size_bytes")})
print(f"DONE! -> {final}")
