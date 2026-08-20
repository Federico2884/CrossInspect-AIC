"""Konfigurasi service, dibaca dari environment (prefix ``AI_``)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # Sisi terpanjang halaman setelah rasterisasi. A4 @ 300 DPI = 2480x3508 px;
    # diumpankan apa adanya ke Qwen2-VL, jumlah visual token-nya membuat
    # inference CPU-only tidak realistis. 300 DPI tetap dipakai supaya teks
    # kecil tidak hancur, lalu hasilnya diperkecil untuk model.
    render_max_long_edge: int = 1600

    # Engine aktif: 'mock' (image slim) atau 'qwen2vl' (butuh Dockerfile.ml).
    # Default sengaja mock supaya klien Laravel dan image ringan tidak terpaksa
    # ikut menarik torch hanya untuk menjalankan kontrak.
    engine: str = "mock"
    qwen_model_id: str = "Qwen/Qwen2-VL-2B-Instruct"
    qwen_max_new_tokens: int = 768
    # Batas jumlah piksel yang dilihat model (knob resmi Qwen2-VL lewat
    # qwen-vl-utils). Nilai awal ~1280 visual token; angka finalnya ditentukan
    # setelah latency diukur, bukan ditebak.
    qwen_max_pixels: int = 1_003_520
    qwen_min_pixels: int = 200_704
    # Halaman yang benar-benar diumpankan ke model. Terpisah dari max_pages
    # supaya biaya inference bisa dibatasi tanpa mengubah batas render.
    qwen_max_model_pages: int = 10

    # Jumlah thread BLAS/OMP. Di-set juga sebagai ENV di Dockerfile supaya
    # library yang membaca env saat import sudah melihat nilai yang benar.
    omp_num_threads: int = 4

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
