<?php

namespace App\Jobs;

use App\Models\Document;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use Throwable;

/**
 * Memanggil service AI di luar siklus request.
 *
 * Alasannya waktu: satu halaman padat terukur ~300 detik dengan engine asli,
 * sehingga menahan request HTTP sampai selesai berarti browser menggantung
 * belasan menit untuk dokumen banyak halaman.
 */
class ParseDocument implements ShouldQueue
{
    use Queueable;

    /**
     * Default Laravel 60 detik — jauh di bawah satu halaman pun.
     *
     * PENTING: ``retry_after`` pada koneksi antrean harus LEBIH BESAR dari
     * angka ini. Kalau tidak, antrean menganggap job-nya mati saat masih
     * menunggu model, lalu menyerahkannya ke worker kedua: dokumen yang sama
     * dibaca dua kali dan hasil yang lebih lambat menimpa yang lebih dulu.
     */
    public int $timeout = 900;

    /**
     * Sekali jalan saja. Membaca ulang dokumen yang gagal berarti membayar
     * beberapa menit inference lagi untuk kegagalan yang hampir pasti sama.
     */
    public int $tries = 1;

    public function __construct(public Document $document) {}

    public function handle(): void
    {
        $this->document->update([
            'status' => Document::STATUS_PROCESSING,
            'started_at' => now(),
        ]);

        $path = Storage::disk('local')->path($this->document->stored_path);

        $pending = Http::timeout((int) config('services.ai.timeout'))
            ->attach('file', file_get_contents($path), $this->document->original_filename);

        try {
            $response = $pending->post(
                rtrim((string) config('services.ai.url'), '/').'/document/parse',
                $this->document->scenario ? ['scenario' => $this->document->scenario] : []
            );
        } catch (ConnectionException $e) {
            $this->fail_with([
                'code' => 'SERVICE_UNREACHABLE',
                'message' => 'Tidak bisa menghubungi service AI. Pastikan container `ai` hidup. '
                    .'Dengan engine Qwen2-VL, permintaan pertama juga menunggu model dimuat.',
                'detail' => $e->getMessage(),
            ]);

            return;
        }

        // Parse yang buruk tetap 200 + warnings[]; hanya request yang gagal
        // memakai amplop {"error": {...}}. Lihat CONTRACT.md.
        if ($response->failed()) {
            $this->fail_with(
                $response->json('error') ?? [
                    'code' => 'HTTP_'.$response->status(),
                    'message' => 'Service AI menolak berkas ini.',
                    'detail' => null,
                ]
            );

            return;
        }

        $this->document->update([
            'status' => Document::STATUS_DONE,
            'response' => $response->json(),
            'error' => null,
            'finished_at' => now(),
        ]);
    }

    /**
     * Dipanggil saat job dibunuh timeout atau melempar di luar dugaan.
     */
    public function failed(?Throwable $exception): void
    {
        $this->fail_with([
            'code' => 'JOB_FAILED',
            'message' => 'Pembacaan dokumen berhenti sebelum selesai.',
            'detail' => $exception?->getMessage(),
        ]);
    }

    private function fail_with(array $error): void
    {
        $this->document->update([
            'status' => Document::STATUS_FAILED,
            'error' => $error,
            'finished_at' => now(),
        ]);
    }
}
