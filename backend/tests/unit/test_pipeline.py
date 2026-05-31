from app.workers.pipeline import ConversationPipeline


def test_start_from_transcript_builds_analysis_to_video_chain(mocker) -> None:
    analysis_sig = object()
    video_sig = object()
    analysis_task = mocker.Mock()
    video_task = mocker.Mock()
    analysis_task.si.return_value = analysis_sig
    video_task.si.return_value = video_sig

    mocker.patch("app.workers.analysis_worker.run_analysis_task", analysis_task)
    mocker.patch("app.workers.video_worker.run_video_generation_task", video_task)

    fake_result = mocker.Mock(id="chain-task-1")
    fake_pipeline = mocker.Mock()
    fake_pipeline.apply_async.return_value = fake_result
    chain_mock = mocker.patch("app.workers.pipeline.chain", return_value=fake_pipeline)

    task_id = ConversationPipeline.start_from_transcript("job-123")

    assert task_id == "chain-task-1"
    analysis_task.si.assert_called_once_with("job-123")
    video_task.si.assert_called_once_with("job-123")
    chain_mock.assert_called_once_with(analysis_sig, video_sig)
    fake_pipeline.apply_async.assert_called_once()
