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
    # qwen-vl-utils). 1_003_520 px = ~1260 visual token untuk halaman A4.
    #
    # Cap dibiarkan tinggi karena menurunkannya ternyata tidak membeli apa-apa.
    # Tiga dokumen bertabel 10 baris, detik & (nama+jumlah benar)/10:
    #
    #                    ~1260 token      ~494 token
    #   sj_0029 PDF      254 s  10/10     177 s   9/10
    #   sj_0029 foto     250 s  10/10     176 s   7/10
    #   sj_0030 PDF      185 s   0/10     186 s   0/10
    #   sj_0030 foto     168 s   4/10     155 s   0/10
    #   sj_0043 PDF      200 s  10/10     198 s   9/10
    #   sj_0043 foto     176 s   2/10     191 s   8/10
    #
    # Hanya sj_0029 yang jelas lebih cepat saat cap diturunkan; pada dua dokumen
    # lain waktunya praktis sama. Sebabnya: yang memakan waktu adalah menuliskan
    # JSON baris per baris, bukan melihat gambarnya. Jadi memperkecil gambar
    # menukar akurasi dengan kecepatan yang sering tidak muncul.
    #
    # Angka akurasi di atas memakai pencocokan string persis dan hanya 3 dokumen
    # — indikator kasar, bukan metrik. Perhatikan sj_0030 (0/10 di semua cap,
    # padahal JSON-nya valid) dan sj_0043 foto (nama 8/10 tapi nama+jumlah
    # 2/10): keduanya pertanyaan untuk evaluasi step 5, bukan bukti soal cap.
    qwen_max_pixels: int = 1_003_520
    qwen_min_pixels: int = 200_704
    # Halaman yang benar-benar diumpankan ke model. Terpisah dari max_pages
    # supaya biaya inference bisa dibatasi tanpa mengubah batas render.
    qwen_max_model_pages: int = 10

    # Ambang LOW_CONFIDENCE_ITEM. Sebelumnya 0.55 dan tidak pernah sekali pun
    # menyala: dari 165 baris terukur, skor terendah 0.842 dan 144 di antaranya
    # membulat ke 1.0 — model percaya diri bahkan saat salah. Warning yang tidak
    # bisa menyala lebih buruk daripada tidak ada, karena tetap dijanjikan
    # kontrak dan tetap digambar UI.
    #
    # 0.95 menandai sekitar 13% baris paling ragu. Itu alat bantu tinjau, BUKAN
    # detektor kesalahan: pada sampel yang sama ia menangkap 4 dari 10 baris
    # salah dan ikut menandai 17 baris yang sebenarnya benar. Angkanya juga
    # diturunkan dari 10 baris salah saja — terlalu sedikit untuk dipercaya, dan
    # ditinjau ulang setelah evaluasi penuh 200 dokumen.
    low_confidence_threshold: float = 0.95

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
