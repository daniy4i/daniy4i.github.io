from collections import defaultdict

@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_job",
    queue="video",
    autoretry_for=(Exception,),
    retry_backoff=5,
    retry_kwargs={"max_retries": 3},
)
def process_job(self, job_id: int):

    db = SessionLocal()

    try:
        job = db.get(Job, job_id)
        if not job:
            logger.warning(f"Job {job_id} not found.")
            return

        job.status = "running"
        db.commit()

        if cv2 is None:
            raise RuntimeError("OpenCV not available")

        logger.info(f"Processing job {job_id}")

        start_time = time.time()

        with tempfile.TemporaryDirectory() as tmpdir:

            input_path = Path(tmpdir) / "input.mp4"
            download_file(job.storage_key, str(input_path))

            cap = cv2.VideoCapture(str(input_path))
            if not cap.isOpened():
                raise RuntimeError("Failed to open video")

            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            raw_output_path = Path(tmpdir) / "annotated_raw.mp4"

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(
                str(raw_output_path),
                fourcc,
                fps,
                (width, height),
            )

            model = load_yolo_model()
            if model is None:
                raise RuntimeError("YOLO model failed to load")

            # 🔥 TRACK MEMORY FIX
            track_history = defaultdict(list)

            frame_index = 0
            clip_id = "main"

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                timestamp_s = frame_index / fps

                tracks = track_frame(
                    model,
                    frame,
                    clip_id=clip_id,
                    timestamp_s=timestamp_s,
                    frame_width=width,
                    frame_height=height,
                )

                # ✅ pass track_history properly
                annotated = annotate_frame(frame, tracks, track_history)
                writer.write(annotated)

                frame_index += 1

            cap.release()
            writer.release()

            preview_path = Path(tmpdir) / "preview_tracking.mp4"
            _encode_preview_h264(str(raw_output_path), str(preview_path))

            with open(preview_path, "rb") as f:
                upload_bytes(
                    key=f"jobs/{job.id}/preview_tracking.mp4",
                    data=f.read(),
                    content_type="video/mp4",
                )

        duration_s = time.time() - start_time

        job.status = "completed"
        job.duration_s = duration_s
        db.commit()

        if job.org_id:
            record_job_processed(db, job.org_id, duration_s=duration_s)

        logger.info(f"Job {job_id} completed successfully.")

    except Exception as exc:
        logger.exception(f"Job {job_id} failed: {exc}")
        job.status = "failed"
        db.commit()
        raise

    finally:
        db.close()
