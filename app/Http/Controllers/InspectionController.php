<?php

namespace App\Http\Controllers;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Response;
use Illuminate\Http\Request;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Http;
use Illuminate\View\View;

/**
 * Alur utama CrossInspect: satu dokumen, satu foto, satu vonis.
 *
 * Halaman ini memanggil tiga endpoint service AI secara berurutan dalam satu
 * request. Urutannya disengaja — vision lebih dulu karena ia menjawab dalam
 * milidetik, jadi service yang mati atau berkas yang ditolak ketahuan sebelum
 * pengguna menunggu inference dokumen yang bisa memakan menit.
 *
 * Seperti DocumentParseController, JSON dari service diteruskan apa adanya ke
 * view. Memetakannya ke objek PHP hanya menciptakan tempat kedua yang bisa
 * menyimpang dari kontrak di ai/app/modules/.
 */
class InspectionController extends Controller
{
    /**
     * Skenario milik engine mock Modul 2. Diabaikan begitu YOLO aktif.
     *
     * @see ai/app/modules/vision/engines/mock.py
     */
    public const VISION_SCENARIOS = [
        'clean_stack',
        'partial_occlusion',
        'single_item',
        'crowded',
        'low_confidence',
        'empty',
        'low_resolution',
    ];

    public function create(): View
    {
        return view('inspections.create', [
            'documentScenarios' => DocumentParseController::SCENARIOS,
            'visionScenarios' => self::VISION_SCENARIOS,
        ]);
    }

    public function inspect(Request $request): View
    {
        $validated = $request->validate([
            // Batas 20 MB disamakan dengan service AI supaya penolakan terjadi
            // di sini, bukan setelah berkas terlanjur dikirim lewat jaringan.
            'document' => ['required', 'file', 'mimes:pdf,png,jpg,jpeg', 'max:20480'],
            // Modul 2 menolak PDF dan menerima WebP — berbeda dari Modul 1.
            'photo' => ['required', 'file', 'mimes:png,jpg,jpeg,webp', 'max:20480'],
            'document_scenario' => [
                'nullable', 'string', 'in:' . implode(',', DocumentParseController::SCENARIOS),
            ],
            'vision_scenario' => [
                'nullable', 'string', 'in:' . implode(',', self::VISION_SCENARIOS),
            ],
        ]);

        $vision = $this->parse(
            '/vision/inspect',
            $validated['photo'],
            $validated['vision_scenario'] ?? null,
            'memeriksa foto barang'
        );
        if (is_array($vision) && isset($vision['failure'])) {
            return view('inspections.result', $vision);
        }

        $document = $this->parse(
            '/document/parse',
            $validated['document'],
            $validated['document_scenario'] ?? null,
            'membaca dokumen'
        );
        if (is_array($document) && isset($document['failure'])) {
            return view('inspections.result', $document);
        }

        $verdict = $this->reconcile($document, $vision);
        if (isset($verdict['failure'])) {
            return view('inspections.result', $verdict);
        }

        return view('inspections.result', [
            'verdict' => $verdict,
            'document' => $document,
            'vision' => $vision,
            'documentName' => $validated['document']->getClientOriginalName(),
            'photoName' => $validated['photo']->getClientOriginalName(),
        ]);
    }

    /**
     * Unggah satu berkas ke endpoint modul, kembalikan JSON-nya.
     *
     * Mengembalikan array ber-key `failure` bila gagal, supaya pemanggil bisa
     * berhenti tanpa exception — kegagalan di sini normal (service mati, berkas
     * ditolak), bukan keadaan luar biasa.
     */
    private function parse(string $path, UploadedFile $file, ?string $scenario, string $step): array
    {
        try {
            $response = Http::timeout((int) config('services.ai.timeout'))
                ->attach('file', file_get_contents($file->getRealPath()), $file->getClientOriginalName())
                ->post(
                    rtrim((string) config('services.ai.url'), '/') . $path,
                    $scenario ? ['scenario' => $scenario] : []
                );
        } catch (ConnectionException $e) {
            return $this->unreachable($step, $e->getMessage());
        }

        return $response->failed() ? $this->rejected($response, $step) : $response->json();
    }

    /** Vonis akhir: JSON, bukan unggahan — Modul 3 tidak menyentuh model. */
    private function reconcile(array $document, array $vision): array
    {
        try {
            $response = Http::timeout((int) config('services.ai.timeout'))
                ->post(
                    rtrim((string) config('services.ai.url'), '/') . '/crosscheck',
                    ['document' => $document, 'vision' => $vision]
                );
        } catch (ConnectionException $e) {
            return $this->unreachable('mencocokkan hasil', $e->getMessage());
        }

        return $response->failed() ? $this->rejected($response, 'mencocokkan hasil') : $response->json();
    }

    private function unreachable(string $step, string $detail): array
    {
        return [
            'failure' => "Tidak bisa menghubungi service AI saat {$step}. Pastikan container `ai` hidup. "
                . 'Saat memakai engine Qwen2-VL, permintaan pertama juga menunggu model dimuat.',
            'detail' => $detail,
        ];
    }

    private function rejected(Response $response, string $step): array
    {
        return [
            'failure' => $response->json('error.message', "Service AI menolak permintaan saat {$step}."),
            'detail' => $response->json('error.detail'),
            'code' => $response->json('error.code'),
            'status' => $response->status(),
        ];
    }
}
