"""API entry point. Run CV independently with `python worker.py`."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.repository import Repository
from backend.routes.jobs import router as jobs_router
from backend.routes.uploads import router as uploads_router
from backend.services.media import validate_video
from backend.services.validation import ValidationService


def create_app(settings=None, *, validator=validate_video):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        settings.prepare_directories()
        app.state.settings = settings
        app.state.repository = Repository(settings.database_path)
        app.state.validation = ValidationService(app.state.repository, settings, validator)
        for upload_id in app.state.repository.pending_uploads(recover=True):
            app.state.validation.submit(upload_id)
        try:
            yield
        finally:
            app.state.validation.close()

    app = FastAPI(title="People in Zone Monitor", version="0.1.0", lifespan=lifespan)
    app.include_router(uploads_router)
    app.include_router(jobs_router)
    return app


app = create_app()
