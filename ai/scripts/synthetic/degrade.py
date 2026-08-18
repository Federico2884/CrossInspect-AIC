"""Rasterisasi PDF + degradasi ala hasil scan/foto (Augraphy).

Model nanti tidak akan melihat PDF bersih: petugas gudang memotret surat jalan
dengan HP, miring sedikit, di bawah lampu gudang, kertasnya terlipat bekas
dilipat tiga. Eval set berisi PDF sempurna akan memberi angka akurasi yang
terlalu optimistis.

Degradasi dibagi tiga tingkat supaya hasil evaluasi step 4 bisa dipecah
per-tingkat ("akurasi turun berapa saat fotonya jelek?"), bukan cuma satu
angka rata-rata yang menyembunyikan kelemahan model.

Catatan: rasterisasi 300 DPI di modul ini berdiri sendiri dan TIDAK
menggantikan ``app/rendering.py`` (step 2) yang belum ada di repo ini.
"""

from __future__ import annotations

import random
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np

RENDER_DPI = 300
SEVERITIES = ("light", "medium", "heavy")


def rasterize(pdf_path: Path, dpi: int = RENDER_DPI) -> list[np.ndarray]:
    """PDF -> daftar halaman sebagai array BGR (urutan warna yang dipakai Augraphy)."""
    pages: list[np.ndarray] = []
    with fitz.open(pdf_path) as document:
        for page in document:
            pixmap = page.get_pixmap(dpi=dpi)
            frame = np.frombuffer(pixmap.samples, dtype=np.uint8)
            frame = frame.reshape(pixmap.height, pixmap.width, pixmap.n)
            pages.append(frame[:, :, 2::-1] if pixmap.n >= 3 else frame)
    return pages


def _build_pipeline(severity: str, seed: int):
    """Susun pipeline sesuai tingkat keparahan.

    Batasnya jelas: teks harus tetap terbaca manusia. Augmentasi yang lebih
    ganas dari ini menghasilkan gambar yang tidak bisa dijadikan label evaluasi
    — itu bukan eval set yang sulit, itu noise.
    """
    from augraphy import (
        AugraphyPipeline,
        BadPhotoCopy,
        Brightness,
        BrightnessTexturize,
        DirtyDrum,
        DirtyRollers,
        Folding,
        Gamma,
        Geometric,
        InkBleed,
        Jpeg,
        LightingGradient,
        LowInkRandomLines,
        NoiseTexturize,
        ShadowCast,
        SubtleNoise,
    )

    random.seed(seed)
    np.random.seed(seed % (2**32))

    if severity == "light":
        # Scan kantor yang rapi.
        ink = [InkBleed(intensity_range=(0.1, 0.25), p=0.5)]
        paper = [
            BrightnessTexturize(texturize_range=(0.9, 0.99), p=0.5),
            LightingGradient(direction=random.randint(0, 360), p=0.4),
        ]
        post = [
            SubtleNoise(subtle_range=random.randint(4, 8), p=0.6),
            Gamma(gamma_range=(0.9, 1.1), p=0.4),
            Jpeg(quality_range=(75, 92), p=0.6),
        ]
    elif severity == "medium":
        # Foto HP yang wajar: sedikit miring, pencahayaan tidak rata.
        ink = [
            InkBleed(intensity_range=(0.2, 0.4), p=0.7),
            LowInkRandomLines(count_range=(3, 8), p=0.3),
        ]
        paper = [
            BadPhotoCopy(noise_type=random.choice((1, 2, 3)), p=0.4),
            NoiseTexturize(sigma_range=(3, 8), p=0.5),
            BrightnessTexturize(texturize_range=(0.85, 0.97), p=0.6),
            LightingGradient(direction=random.randint(0, 360), p=0.8),
        ]
        post = [
            Geometric(rotate_range=(-2, 2), p=0.7),
            ShadowCast(shadow_opacity_range=(0.15, 0.4), p=0.5),
            DirtyDrum(line_width_range=(1, 3), p=0.3),
            SubtleNoise(subtle_range=random.randint(6, 14), p=0.7),
            Brightness(brightness_range=(0.8, 1.1), p=0.6),
            Gamma(gamma_range=(0.8, 1.25), p=0.5),
            Jpeg(quality_range=(50, 80), p=0.8),
        ]
    else:  # heavy
        # Fotokopi lusuh, kertas terlipat, cahaya gudang seadanya.
        ink = [
            InkBleed(intensity_range=(0.3, 0.6), p=0.8),
            LowInkRandomLines(count_range=(5, 12), p=0.5),
        ]
        paper = [
            BadPhotoCopy(noise_type=random.choice((1, 2, 3, 4)), p=0.7),
            NoiseTexturize(sigma_range=(5, 12), p=0.7),
            BrightnessTexturize(texturize_range=(0.8, 0.95), p=0.7),
            LightingGradient(direction=random.randint(0, 360), p=0.9),
        ]
        post = [
            Folding(fold_count=random.randint(1, 3), fold_noise=0.02, p=0.6),
            Geometric(rotate_range=(-4, 4), p=0.8),
            ShadowCast(shadow_opacity_range=(0.25, 0.55), p=0.7),
            # DirtyDrum/DirtyRollers ditahan rendah: pada 300 DPI keduanya
            # menghasilkan pita hitam yang menelan satu baris tabel penuh.
            # Baris yang hilang bukan "contoh sulit" — ground truth-nya jadi
            # label yang tidak adil karena manusia pun tak bisa membacanya.
            DirtyRollers(p=0.12),
            DirtyDrum(line_width_range=(1, 2), p=0.15),
            SubtleNoise(subtle_range=random.randint(10, 20), p=0.8),
            Brightness(brightness_range=(0.7, 1.05), p=0.7),
            Gamma(gamma_range=(0.7, 1.35), p=0.6),
            Jpeg(quality_range=(35, 65), p=0.9),
        ]

    return AugraphyPipeline(ink_phase=ink, paper_phase=paper, post_phase=post)


def degrade(page: np.ndarray, seed: int, severity: str = "medium") -> np.ndarray:
    """Terapkan pipeline. Bila Augraphy gagal, kembalikan halaman apa adanya.

    Sebagian augmentasi Augraphy sensitif terhadap ukuran gambar dan sesekali
    melempar; satu halaman gagal tidak boleh menggagalkan generasi dataset.
    """
    if severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {SEVERITIES}, got {severity!r}")

    pipeline = _build_pipeline(severity, seed)
    try:
        result = pipeline(page)
    except Exception:
        return page

    # API Augraphy pernah berubah: versi lama mengembalikan dict berisi 'output'.
    if isinstance(result, dict):
        result = result.get("output", page)
    return np.asarray(result, dtype=np.uint8)


def save_image(page: np.ndarray, destination: Path, quality: int = 90) -> Path:
    import cv2

    destination.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destination), page, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return destination
