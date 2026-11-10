def finish_ui_job(app):
    """AppTest has no wall-clock fragment scheduler; explicitly refresh when done."""
    job=app.session_state['optical_job']
    if not job.done.wait(30):raise AssertionError('Video job timed out')
    return app.run()
