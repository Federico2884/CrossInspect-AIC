"""Engine Qwen2-VL — inference CPU-only untuk Modul 1.

Satu-satunya modul di Modul 1 yang mengimpor torch. ``service.get_engine()``
mengimpornya di dalam cabang, jadi image slim tidak pernah menyentuh berkas ini.

Alur per request: render halaman -> satu panggilan model per halaman -> JSON
diurai oleh ``extraction`` -> digabung jadi satu ``ParseResponse``.

**Per halaman, bukan sekaligus.** Menjejalkan sepuluh halaman ke satu prompt
melipatgandakan visual token sampai di luar kemampuan CPU, dan ``source_page``
jadi harus ditebak model. Satu panggilan per halaman membuat nomor halaman
diketahui dari konstruksinya.

Bobot model dimuat sekali lewat cache modul; memuat ulang 4 GB tiap request
jelas bukan pilihan. Panggilan pertama karena itu jauh lebih lambat.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import torch
from PIL import Image
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

from app.core.config import get_settings
from app.modules.document.engines.base import DocumentPayload
from app.modules.document.extraction import (
    ExtractedPage,
    TokenSpan,
    assemble_response,
    build_token_spans,
    extract_page,
)
from app.modules.document.rendering import render_pages
from app.modules.document.schemas import ParseResponse

logger = logging.getLogger(__name__)

PROMPT = """Kamu membaca dokumen logistik Indonesia (Surat Jalan atau Invoice).

Keluarkan HANYA satu objek JSON, tanpa penjelasan dan tanpa pagar markdown,
dengan bentuk persis seperti ini:

{
  "document_type": "SURAT_JALAN" | "INVOICE" | "UNKNOWN",
  "document_number": "nomor dokumen apa adanya",
  "document_date": "tanggal apa adanya seperti tertulis",
  "sender": "nama pengirim",
  "recipient": "nama penerima",
  "items": [
    {
      "item_name": "nama barang",
      "sku": "kode barang bila ada, selain itu null",
      "quantity": angka,
      "unit_raw": "satuan persis seperti tertulis, mis. Karton, Dus, Zak, Ball",
      "quantity_per_unit": isi per satuan bila tertulis (mis. 12 pada "@ 12 pcs"), null bila tidak
    }
  ]
}

Aturan:
- Salin teks apa adanya. Jangan menerjemahkan dan jangan merapikan satuan.
- "quantity" adalah jumlah dalam satuan pada "unit_raw", bukan jumlah pcs.
- Sertakan SEMUA baris barang yang terlihat di halaman ini.
- Bila sebuah field tidak ada di halaman ini, isi null.
- Bila halaman ini tidak memuat tabel barang, kembalikan "items": [].
"""


@lru_cache(maxsize=1)
def _load(model_id: str):
    """Muat model + processor sekali per proses."""
    logger.info("memuat %s (CPU)", model_id)
    settings = get_settings()
    processor = AutoProcessor.from_pretrained(
        model_id,
        min_pixels=settings.qwen_min_pixels,
        max_pixels=settings.qwen_max_pixels,
    )
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=torch.float32,  # CPU tidak punya jalur bf16 yang cepat
        device_map=None,
    )
    model.eval()
    logger.info("model siap")
    return model, processor


def _read_page(model, processor, image: Image.Image, page_number: int) -> ExtractedPage:
    """Satu halaman -> struktur, lengkap dengan confidence dari logprob."""
    settings = get_settings()
    # min/max_pixels ditaruh di pesan, bukan hanya di processor: qwen-vl-utils
    # sudah mengubah ukuran gambar sebelum processor melihatnya, dan nilai di
    # sinilah yang benar-benar menentukan jumlah visual token — knob utama
    # untuk latency di CPU.
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "image": image,
                    "min_pixels": settings.qwen_min_pixels,
                    "max_pixels": settings.qwen_max_pixels,
                },
                {"type": "text", "text": PROMPT},
            ],
        }
    ]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )

    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=settings.qwen_max_new_tokens,
            do_sample=False,  # ekstraksi butuh determinisme, bukan variasi
            # generation_config bawaan Qwen menyetel temperature/top_p/top_k.
            # Ketiganya hanya berlaku saat sampling, jadi dengan do_sample=False
            # tidak ada warper yang dipasang dan nilainya tidak dipakai sama
            # sekali — dikosongkan supaya transformers berhenti memperingatkan
            # tiga kali per halaman.
            temperature=None,
            top_p=None,
            top_k=None,
            output_scores=True,
            return_dict_in_generate=True,
        )

    prompt_length = inputs.input_ids.shape[1]
    new_ids = generated.sequences[0][prompt_length:]
    decoded = processor.decode(new_ids, skip_special_tokens=True)
    spans = _token_spans(processor, new_ids, generated.scores)

    return extract_page(decoded, page_number, spans)


def _token_spans(processor, new_ids, scores) -> list[TokenSpan]:
    """Peluang tiap token terpilih, dipetakan ke offset karakter teks hasil decode.

    Dipakai sebagai confidence: bukan kalibrasi sempurna, tetapi mencerminkan
    keraguan model itu sendiri dan tidak butuh inference tambahan.
    """
    if not scores:
        return []

    probabilities: list[float] = []
    for step, logits in enumerate(scores):
        if step >= len(new_ids):
            break
        distribution = torch.softmax(logits[0].float(), dim=-1)
        probabilities.append(float(distribution[int(new_ids[step])].item()))

    # Decode bertahap, bukan per token sendiri-sendiri. Tokenizer Qwen bekerja
    # pada level byte, jadi satu karakter multi-byte bisa terbelah di dua token;
    # men-decode token secara terpisah menghasilkan karakter pengganti dan
    # offset yang meleset diam-diam. Selisih antar prefix dijamin menyambung
    # persis menjadi teks utuh.
    tokenizer = processor.tokenizer
    pieces: list[str] = []
    previous = ""
    for index in range(len(probabilities)):
        current = tokenizer.decode(new_ids[: index + 1], skip_special_tokens=True)
        pieces.append(current[len(previous) :])
        previous = current

    return build_token_spans(pieces, probabilities)


class QwenEngine:
    """Engine asli. ``meta.engine`` berisi id model, sesuai janji kontrak."""

    def __init__(self) -> None:
        settings = get_settings()
        self.name = settings.qwen_model_id
        self._model_id = settings.qwen_model_id

    def parse(self, payload: DocumentPayload) -> ParseResponse:
        settings = get_settings()
        rendered = render_pages(payload.content, payload.media_type)

        model, processor = _load(self._model_id)

        # Batas model bisa lebih ketat daripada batas render. Yang dilaporkan
        # sebagai page_count adalah halaman yang benar-benar dibaca — itu arti
        # page_count di CONTRACT.md, dan itu pula yang membuat truncated jujur.
        model_pages = rendered.pages[: settings.qwen_max_model_pages]

        pages: list[ExtractedPage] = []
        for offset, image in enumerate(model_pages):
            page_number = offset + 1
            try:
                pages.append(_read_page(model, processor, image, page_number))
            except Exception:
                # Satu halaman gagal tidak boleh menjatuhkan seluruh dokumen;
                # halaman itu dicatat sebagai tidak terbaca lalu jalan terus.
                logger.exception("halaman %s gagal dibaca", page_number)
                pages.append(ExtractedPage(ok=False, raw_text=""))

        response = assemble_response(
            pages=pages,
            page_count=len(model_pages),
            truncated=rendered.total_pages > len(model_pages),
            total_pages=rendered.total_pages,
            engine_name=self.name,
        )

        if settings.debug:
            # Keluaran mentah model hanya bisa dilihat dari sini; begitu JSON
            # gagal diurai, jejaknya hilang dan yang tersisa cuma "baris tidak
            # ketemu" tanpa sebab. Ditaruh di meta.debug yang memang sudah ada
            # di kontrak, dan tetap null selama AI_DEBUG belum dinyalakan —
            # bentuk response tidak berubah.
            response.meta.debug = {
                "raw_pages": [page.raw_text for page in pages],
                "rendered_pages": rendered.page_count,
                "total_pages": rendered.total_pages,
            }

        return response
