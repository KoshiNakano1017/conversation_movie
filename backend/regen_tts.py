"""ハカセの TTS を再生成して音声付き動画を作り直す"""
import sys
sys.path.insert(0, ".")
import logging
logging.disable(logging.CRITICAL)
from pathlib import Path
from app.models.job import JobStatus
from app.services.job_service import update_job_status
from app.services.tts_service import TTSService
from app.services.video_service import VideoService
from app.services.storage_service import StorageService
from app.workers.video_worker import _fetch_required_data, _save_video_record

JOB = "65ce63c2-6167-40fc-bd30-03551002a8d9"
title, uid, analysis, srt, scripts, audio = _fetch_required_data(JOB)

svc = VideoService()
vd = svc.build_video_data(JOB, title, analysis, [], scripts)

job_dir = Path("C:/Users/nakano-ko/Desktop/ConversationMovie/media/video") / JOB
subtitled = job_dir / "subtitled_full.mp4"
print("base video:", subtitled.name, subtitled.stat().st_size // 1024, "KB")

print("TTS音声生成中（リトライ付き）...")
tts = TTSService()
scripts_audio = tts.generate_for_scripts(vd.avatar_scripts, job_dir)
for s in scripts_audio:
    ap = s.get("audio_path")
    sz = Path(ap).stat().st_size if ap else 0
    char = s["character_name"]
    sec = s["section"]
    print(f"  {char} {sec}: {sz // 1024}KB")

print("音声合成中...")
final = svc.mix_tts_audio(subtitled, scripts_audio)
print("完了:", final)

thumb = svc.extract_thumbnail(final, 4.0)
update_job_status(JOB, JobStatus.GENERATING_VIDEO, progress=92)
meta = svc.get_video_metadata(final)
st = StorageService()
_save_video_record(JOB, uid, st.get_video_url(JOB, final.name), st.get_thumbnail_url(JOB), meta)
update_job_status(JOB, JobStatus.COMPLETED, progress=100)
print("DONE! ->", final)
