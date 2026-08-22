"""Router Modul 2 — Physical Inspection.

Sengaja tipis: validasi dan orkestrasi ada di ``service.py`` supaya logic-nya
bisa diuji tanpa HTTP. Pola yang sama dengan router Modul 1.
"""

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.core.config import get_settings
from app.modules.vision.engines import yolo
from app.modules.vision.engines.mock import SCENARIOS
from app.modules.vision.schemas import InspectResponse
from app.modules.vision.service import inspect_image

router = APIRouter(prefix="/vision", tags=["vision"])


@router.get(
    "/engine",
    summary="Engine mana yang sedang melayani deteksi",
)
def engine_status() -> dict:
    """Menjawab 'ini hasil model asli atau mock?' tanpa perlu mengirim foto.

    Terpisah dari ``/health`` karena health harus tetap murah — ia dipakai
    HEALTHCHECK tiap 15 detik, sedangkan ini menyentuh filesystem.
    """
    settings = get_settings()
    available = yolo.is_available()
    return {
        "configured": settings.vision_engine,
        "active": "mock" if settings.vision_engine == "mock" or not available else "yolo",
        "yolo_available": available,
        "model_path": str(settings.vision_model_file),
        "model_present": settings.vision_model_file.is_file(),
        "conf_threshold": settings.vision_conf_threshold,
    }


@router.post(
    "/inspect",
    response_model=InspectResponse,
    summary="Hitung kemasan fisik pada foto barang",
    responses={
        413: {"description": "File melebihi batas ukuran"},
        422: {"description": "File kosong, bukan gambar, atau skenario tidak dikenal"},
        503: {"description": "Engine YOLO dipaksa aktif tetapi tidak tersedia"},
    },
)
async def inspect(
    file: Annotated[UploadFile, File(description="PNG, JPEG, atau WebP. Maks 20 MB.")],
    scenario: Annotated[
        str | None,
        Form(description=f"Opsional, khusus engine mock. Pilihan: {', '.join(SCENARIOS)}"),
    ] = None,
) -> InspectResponse:
    content = await file.read()
    return inspect_image(content=content, filename=file.filename, scenario=scenario)
