"""Konfigurasi service, dibaca dari environment (prefix ``AI_``)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Akar service (/srv/ai di dalam container). config.py ada di app/core/.
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore")

    app_name: str = "CrossInspect AI"
    version: str = "0.1.0"
    debug: bool = False

    # Modul 1 — Document Parsing.
    # Batas upload & halaman sengaja dibuat konservatif: inference CPU-only,
    # jadi dokumen raksasa harus ditolak lebih awal daripada bikin request hang.
    max_upload_mb: int = 20
    max_pages: int = 10
    render_dpi: int = 300

    # Jumlah thread BLAS/OMP. Di-set juga sebagai ENV di Dockerfile supaya
    # library yang membaca env saat import sudah melihat nilai yang benar.
    omp_num_threads: int = 4

    # --- Modul 2 — Physical Inspection ---
    # 'auto' memakai YOLO bila ultralytics terpasang DAN bobotnya ada, selain itu
    # jatuh ke mock. Nilai eksplisit dipakai saat ingin memaksa salah satunya,
    # misalnya di test yang tidak boleh menyentuh torch.
    vision_engine: Literal["auto", "yolo", "mock"] = "auto"
    vision_model_path: str = "models/inspection.pt"
    vision_imgsz: int = 640  # harus sama dengan imgsz saat training

    # Ambang yang dipakai notebook training (conf=0.4). Semuanya lewat env supaya
    # bobot hasil training ulang bisa dikalibrasi tanpa menyentuh kode.
    vision_conf_threshold: float = 0.40
    vision_min_resolution: int = 640
    vision_occlusion_iou: float = 0.15
    vision_occlusion_ratio_alert: float = 0.30
    vision_unreliable_below: float = 0.55
    vision_low_confidence_margin: float = 0.10

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def vision_model_file(self) -> Path:
        path = Path(self.vision_model_path)
        return path if path.is_absolute() else BASE_DIR / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
