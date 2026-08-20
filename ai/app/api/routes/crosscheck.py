"""Router Modul 3 — Cross-Check Engine.

Sengaja tipis, sama seperti router modul lain: seluruh logika ada di
``service.py`` supaya bisa diuji tanpa HTTP.

Endpoint ini menerima JSON, bukan unggahan berkas — ia tidak pernah menyentuh
model, hanya merekonsiliasi dua respons yang sudah jadi.
"""

from fastapi import APIRouter

from app.modules.crosscheck.schemas import CrossCheckRequest, CrossCheckResponse
from app.modules.crosscheck.service import cross_check

router = APIRouter(tags=["crosscheck"])


@router.post(
    "/crosscheck",
    response_model=CrossCheckResponse,
    summary="Rekonsiliasi hasil Modul 1 dan Modul 2",
    responses={422: {"description": "Body tidak sesuai bentuk kontrak hulu"}},
)
def crosscheck(payload: CrossCheckRequest) -> CrossCheckResponse:
    return cross_check(payload)
