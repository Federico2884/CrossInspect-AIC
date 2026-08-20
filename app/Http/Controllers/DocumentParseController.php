<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use Illuminate\View\View;

/**
 * Antarmuka uji untuk Modul 1 (Document Parsing).
 *
 * Halaman ini sengaja tipis: bentuk JSON dari service AI langsung diteruskan
 * ke view. Memetakannya ke objek PHP hanya akan menciptakan tempat kedua yang
 * bisa menyimpang dari CONTRACT.md.
 */
class DocumentParseController extends Controller
{
    /**
     * Skenario milik engine mock. Diabaikan begitu AI_ENGINE=qwen2vl.
     *
     * @see ai/app/modules/document/engines/mock.py
     */
    public const SCENARIOS = [
        'clean_surat_jalan',
        'invoice',
        'multi_page',
        'mixed_units',
        'low_confidence',
        'missing_fields',
        'unknown_type',
    ];

    public function create(): View
    {
        return view('documents.create', ['scenarios' => self::SCENARIOS]);
    }

    public function parse(Request $request): View
    {
        $validated = $request->validate([
            // Batas 20 MB disamakan dengan service AI supaya penolakan terjadi
            // di sini, bukan setelah file terlanjur dikirim lewat jaringan.
            'file' => ['required', 'file', 'mimes:pdf,png,jpg,jpeg', 'max:20480'],
            'scenario' => ['nullable', 'string', 'in:' . implode(',', self::SCENARIOS)],
        ]);

        $file = $validated['file'];
        $scenario = $validated['scenario'] ?? null;

        $pending = Http::timeout((int) config('services.ai.timeout'))
            ->attach('file', file_get_contents($file->getRealPath()), $file->getClientOriginalName());

        try {
            $response = $pending->post(
                rtrim((string) config('services.ai.url'), '/') . '/document/parse',
                $scenario ? ['scenario' => $scenario] : []
            );
        } catch (ConnectionException $e) {
            return view('documents.result', [
                'failure' => 'Tidak bisa menghubungi service AI. Pastikan container `ai` hidup. '
                    . 'Saat memakai engine Qwen2-VL, permintaan pertama juga menunggu model dimuat.',
                'detail' => $e->getMessage(),
            ]);
        }

        // Parse yang buruk tetap 200 + warnings[]; hanya request yang gagal
        // yang memakai envelope {"error": {...}}. Lihat CONTRACT.md.
        if ($response->failed()) {
            return view('documents.result', [
                'failure' => $response->json('error.message', 'Service AI menolak berkas ini.'),
                'detail' => $response->json('error.detail'),
                'code' => $response->json('error.code'),
                'status' => $response->status(),
            ]);
        }

        return view('documents.result', [
            'result' => $response->json(),
            'filename' => $file->getClientOriginalName(),
        ]);
    }
}
