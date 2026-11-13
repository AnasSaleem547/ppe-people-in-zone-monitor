"""Fetch standard Ultralytics YOLO26 medium weights once, then reuse them."""
from pathlib import Path
import shutil


def ensure_model(settings):
    target = Path(settings.model_path).expanduser().resolve()
    if target.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    from ultralytics.utils.downloads import attempt_download_asset
    official_target = target.parent / settings.model_name
    try:
        downloaded = Path(attempt_download_asset(str(official_target)))
        if not downloaded.is_file():
            raise FileNotFoundError('Ultralytics did not provide the model file.')
        if downloaded.resolve() != target:
            shutil.copyfile(downloaded, target)
    except Exception as exc:
        raise RuntimeError(f'Could not obtain {settings.model_name}. First startup needs access to the Ultralytics GitHub assets, or a pre-downloaded file at {target}.') from exc
    return target


if __name__ == '__main__':
    from backend.core.config import Settings
    print(ensure_model(Settings()))
