<?php

namespace App\Jobs;

use App\Models\Inspection;
use App\Services\CrossInspectClient;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Storage;
use Throwable;

/**
 * Menjalankan seluruh alur pemeriksaan cross-check di latar belakang.
 *
 * Urutan pemanggilan:
 * 1. /vision/inspect (Modul 2) - Cepat (~ms). Bila foto ditolak, proses langsung berhenti
 *    tanpa membuang waktu untuk inferensi dokumen yang mahal.
 * 2. /document/parse (Modul 1) - Memakan waktu menit pada CPU dengan Qwen2-VL.
 * 3. /crosscheck (Modul 3) - Rekonsiliasi berbasis aturan kontraktual (~ms).
 */
class InspectShipment implements ShouldQueue
{
    use Queueable;

    public int $timeout = 900;

    public int $tries = 1;

    public function __construct(public Inspection $inspection) {}

    public function handle(CrossInspectClient $ai): void
    {
        $this->inspection->update([
            'status' => Inspection::STATUS_PROCESSING_VISION,
            'started_at' => now(),
        ]);

        $photoBytes = Storage::disk('local')->get($this->inspection->photo_stored_path);
        if ($photoBytes === null) {
            $this->fail_with([
                'failure' => 'Berkas foto barang tidak ditemukan di penyimpanan server.',
                'detail' => $this->inspection->photo_stored_path,
            ]);

            return;
        }

        $vision = $ai->upload(
            '/vision/inspect',
            $photoBytes,
            $this->inspection->photo_original_name,
            null,
            'memeriksa foto barang'
        );

        if (CrossInspectClient::failed($vision)) {
            $this->fail_with($vision);

            return;
        }

        $this->inspection->update([
            'status' => Inspection::STATUS_PROCESSING_DOCUMENT,
            'vision_response' => $vision,
        ]);

        $documentBytes = Storage::disk('local')->get($this->inspection->document_stored_path);
        if ($documentBytes === null) {
            $this->fail_with([
                'failure' => 'Berkas dokumen surat jalan tidak ditemukan di penyimpanan server.',
                'detail' => $this->inspection->document_stored_path,
            ]);

            return;
        }

        $document = $ai->upload(
            '/document/parse',
            $documentBytes,
            $this->inspection->document_original_name,
            null,
            'membaca dokumen'
        );

        if (CrossInspectClient::failed($document)) {
            $this->fail_with($document);

            return;
        }

        $this->inspection->update([
            'status' => Inspection::STATUS_RECONCILING,
            'document_response' => $document,
        ]);

        $verdict = $ai->reconcile($document['raw'], $vision['raw']);

        if (CrossInspectClient::failed($verdict)) {
            $this->fail_with($verdict);

            return;
        }

        $this->inspection->update([
            'status' => Inspection::STATUS_DONE,
            'verdict_response' => $verdict,
            'error' => null,
            'finished_at' => now(),
        ]);
    }

    public function failed(?Throwable $exception): void
    {
        $this->fail_with([
            'failure' => 'Pemeriksaan kiriman berhenti sebelum selesai.',
            'detail' => $exception?->getMessage(),
        ]);
    }

    private function fail_with(array $error): void
    {
        $this->inspection->update([
            'status' => Inspection::STATUS_FAILED,
            'error' => $error,
            'finished_at' => now(),
        ]);
    }
}
