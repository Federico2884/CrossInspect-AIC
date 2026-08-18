# Document Parsing API — Contract

Authoritative contract for **Modul 1 (Document Parsing)** of CrossInspect AI.
Enforced by the Pydantic models in [`app/modules/document/schemas.py`](app/modules/document/schemas.py);
if this document and those models ever disagree, the models are the bug.

Audience: whoever writes the Laravel client. You can build against this today —
the endpoint is live and backed by a deterministic mock.

---

## Endpoint

```
POST http://ai:8000/document/parse
Content-Type: multipart/form-data
```

From the host (debugging): `http://localhost:8001/document/parse`.
Interactive schema: `http://localhost:8001/docs`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | file | yes | PDF, PNG, or JPEG. Max **20 MB**. |
| `scenario` | string | no | **Mock only.** Forces a specific fixture — see [Scenarios](#scenarios). Ignored once the real engine lands. |

Format is detected from **magic bytes**, not from the filename or the
`Content-Type` you send. A `.txt` renamed to `.pdf` is rejected.

---

## Response — 200

```json
{
  "document_type": "SURAT_JALAN",
  "document_number": "SJ/2026/08/00161",
  "document_date": "2026-08-15",
  "sender": "PT Cahaya Abadi",
  "recipient": "Toko Sumber Rejeki",
  "page_count": 1,
  "items": [
    {
      "item_name": "Susu UHT Ultra 250ml",
      "sku": "ULT-250",
      "quantity": 10,
      "unit_raw": "Karton",
      "unit_normalized": "karton",
      "quantity_per_unit": 12,
      "total_pieces": 120,
      "source_page": 1
    }
  ],
  "confidence": { "document_number": 0.93, "items": [0.95], "overall": 0.86 },
  "warnings": [
    { "code": "AMBIGUOUS_UNIT", "message": "…", "severity": "warning", "item_index": 2 }
  ],
  "meta": {
    "engine": "mock",
    "device": "cpu",
    "processing_ms": 3,
    "scenario": "mixed_units",
    "debug": null
  }
}
```

### Fields

| Field | Type | Notes |
|---|---|---|
| `document_type` | `SURAT_JALAN` \| `INVOICE` \| `UNKNOWN` | `UNKNOWN` still returns 200 — check `warnings`. |
| `document_number` | string | Empty string when unreadable, never null. |
| `document_date` | string \| null | ISO `YYYY-MM-DD`. Null when absent from the document. |
| `sender` / `recipient` | string \| null | |
| `page_count` | int ≥ 1 | Pages actually processed (capped at 10). |
| `items[]` | array | May be empty. |
| `confidence` | object | `document_number`, `items[]` (parallel to `items`), `overall`. All 0.0–1.0. |
| `warnings[]` | array | Parse-quality problems. **Not** errors. |
| `meta` | object | `engine`, `device` (always `"cpu"`), `processing_ms`, `scenario`, `debug`. |

### Item fields

| Field | Type | Notes |
|---|---|---|
| `item_name` | string | |
| `sku` | string \| null | |
| `quantity` | int ≥ 0 | **In `unit_raw`, not in pieces.** |
| `unit_raw` | string | Verbatim from the document: `Koli`, `Dus`, `Ball`, `Zak`… |
| `unit_normalized` | enum | `pcs` \| `box` \| `karton` \| `koli` \| `kg` \| `lusin` \| `roll` \| `sak` \| `unknown` |
| `quantity_per_unit` | int \| null | Contents per unit, e.g. `12` in "10 karton @ 12 pcs". |
| `total_pieces` | int \| null | `quantity × quantity_per_unit`, when derivable. |
| `source_page` | int ≥ 1 | Never exceeds `page_count`. |

> **Cross-check note.** Modul 2 counts physical cartons. For `10 karton @ 12 pcs`,
> compare against **`quantity` (10)** — not `total_pieces` (120). The split exists
> precisely so neither side has to guess which number it's looking at.

> **Unit note.** `unit_normalized` is a closed enum, so anything unusual becomes
> `unknown` — but `unit_raw` always preserves what the document said. Real Surat
> Jalan use `koli`, `dus`, `zak`, `ball`, `slop`; never key logic off the enum alone
> when it reads `unknown`.

---

## Warnings vs errors

A document that parses **badly** returns **200 with `warnings[]`** — so the UI can
surface uncertainty ("item 3 unclear, please confirm") instead of silently trusting
bad numbers. A request that **fails** returns 4xx with an `error` envelope.

| Code | Severity | Meaning |
|---|---|---|
| `LOW_CONFIDENCE_ITEM` | warning | Item read with low confidence; `item_index` points at it. |
| `MISSING_DOCUMENT_DATE` | warning | No date found; `document_date` is null. |
| `MISSING_FIELD` | info/warning | Some other field could not be extracted. |
| `AMBIGUOUS_UNIT` | warning | `unit_raw` did not map to the enum; `unit_normalized` is `unknown`. |
| `UNRECOGNISED_DOCUMENT_TYPE` | error | Neither Surat Jalan nor Invoice. |
| `PAGE_LIMIT_TRUNCATED` | warning | Document exceeded the 10-page cap. |
| `QUANTITY_MISMATCH` | warning | Stated total disagrees with the computed one. |

Match on `code`. `message` is human-facing Indonesian and may be reworded.

## Errors

```json
{ "error": { "code": "FILE_TOO_LARGE", "message": "File exceeds the 20 MB limit.", "detail": "received 21000000 bytes" } }
```

| HTTP | Code | Cause |
|---|---|---|
| 413 | `FILE_TOO_LARGE` | Over 20 MB. |
| 422 | `EMPTY_FILE` | Zero bytes. |
| 422 | `UNSUPPORTED_FILE_TYPE` | Not PDF/PNG/JPEG by magic bytes. |
| 422 | `UNKNOWN_SCENARIO` | `scenario` not one of the seven. |
| 422 | `INVALID_REQUEST` | Malformed request, e.g. no `file` field. |

The `error` envelope is used for **all** failures — FastAPI's default
`{"detail": …}` shape never leaks through.

---

## Scenarios

Mock-only. Pass `scenario` to force one; omit it and one is chosen deterministically
from a hash of the file bytes, so the same upload always returns the same response.

| `scenario` | What it exercises |
|---|---|
| `clean_surat_jalan` | Happy path, 3 items, high confidence |
| `invoice` | `INVOICE` type with SKUs |
| `multi_page` | 3 pages, items spread across `source_page` |
| `mixed_units` | `karton`/`koli`/`Ball`/`kg`, `quantity_per_unit` arithmetic, `AMBIGUOUS_UNIT` |
| `low_confidence` | Per-item low scores + `LOW_CONFIDENCE_ITEM` |
| `missing_fields` | Null `document_date`/`sender` + warnings, still 200 |
| `unknown_type` | `UNKNOWN`, no items, `error`-severity warnings |

Build the Laravel client against `mixed_units` and `low_confidence` first — the
happy path is the easy one; those two are where cross-check logic actually gets tested.

```bash
curl -F "file=@sample.pdf" -F "scenario=mixed_units" http://localhost:8001/document/parse
```

---

## Stability guarantee

Steps 4–5 replace the mock with Qwen2-VL behind the same interface
([`engines/base.py`](app/modules/document/engines/base.py)). When that happens:

- The response **shape does not change**. Same fields, same types, same enums.
- `meta.engine` flips from `"mock"` to the model id — that is how you tell which
  engine answered.
- `meta.scenario` becomes `null`; the `scenario` field is ignored.
- `meta.device` stays `"cpu"`. The service is CPU-only by design — there is no GPU
  code path, and the ML image asserts this at build time.

Everything else — warning codes, error codes, the `quantity` / `total_pieces` split —
is contract, not implementation detail.
