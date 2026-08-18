"""Router Modul 1 — Document Parsing.

Sengaja tipis: validasi dan orkestrasi ada di ``service.py`` supaya logic-nya
bisa diuji tanpa HTTP.
"""

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.modules.document.engines.mock import SCENARIOS
from app.modules.document.schemas import ParseResponse
from app.modules.document.service import parse_document

router = APIRouter(prefix="/document", tags=["document"])


@router.post(
    "/parse",
    response_model=ParseResponse,
    summary="Ekstrak key-value + line item dari Surat Jalan / Invoice",
    responses={
        413: {"description": "File melebihi batas ukuran"},
        422: {"description": "File kosong, tipe tidak didukung, atau skenario tidak dikenal"},
    },
)
async def parse(
    file: Annotated[UploadFile, File(description="PDF, PNG, atau JPEG. Maks 20 MB.")],
    scenario: Annotated[
        str | None,
        Form(description=f"Opsional, khusus engine mock. Pilihan: {', '.join(SCENARIOS)}"),
    ] = None,
) -> ParseResponse:
    content = await file.read()
    return parse_document(content=content, filename=file.filename, scenario=scenario)
