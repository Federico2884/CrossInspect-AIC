<?php

namespace App\Http\Controllers;

use App\Services\CrossInspectClient;
use Illuminate\Http\Request;
use Illuminate\View\View;

/**
 * Halaman uji skenario — memperagakan alur cross-check tanpa perlu menyiapkan
 * berkas apa pun.
 *
 * Alasan halaman ini terpisah dari muka aplikasi: engine mock mengabaikan isi
 * berkas, tetapi service AI tetap **mewajibkan** field `file`. Menggabungkan
 * keduanya dalam satu formulir memaksa aturan "wajib kecuali kalau…", dan
 * halaman utama jadi menampilkan kendali uji yang tidak relevan bagi petugas.
 *
 * Berkas contoh di `resources/samples/` dikirim di sisi server. Itu bukan
 * akal-akalan: berkas sungguhan tetap melewati validasi ukuran dan magic bytes
 * di service, dan jalur kodenya sama persis dengan halaman utama — hanya
 * sumber berkasnya yang berbeda. Dengan engine asli aktif, berkas contoh itu
 * benar-benar dibaca model.
 */
class ScenarioDemoController extends Controller
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

    private const SAMPLE_DOCUMENT = 'samples/surat-jalan-contoh.pdf';

    private const SAMPLE_PHOTO = 'samples/tumpukan-contoh.jpg';

    public function __construct(private readonly CrossInspectClient $ai) {}

    public function create(): View
    {
        return view('demo.create', [
            'documentScenarios' => DocumentParseController::SCENARIOS,
            'visionScenarios' => self::VISION_SCENARIOS,
        ]);
    }

    public function run(Request $request): View
    {
        $validated = $request->validate([
            'document_scenario' => [
                'nullable', 'string', 'in:' . implode(',', DocumentParseController::SCENARIOS),
            ],
            'vision_scenario' => [
                'nullable', 'string', 'in:' . implode(',', self::VISION_SCENARIOS),
            ],
        ]);

        [$photoBytes, $photoName] = $this->sample(self::SAMPLE_PHOTO);
        $vision = $this->ai->upload(
            '/vision/inspect',
            $photoBytes,
            $photoName,
            $validated['vision_scenario'] ?? null,
            'memeriksa foto barang'
        );
        if (CrossInspectClient::failed($vision)) {
            return view('inspections.result', $vision);
        }

        [$documentBytes, $documentName] = $this->sample(self::SAMPLE_DOCUMENT);
        $document = $this->ai->upload(
            '/document/parse',
            $documentBytes,
            $documentName,
            $validated['document_scenario'] ?? null,
            'membaca dokumen'
        );
        if (CrossInspectClient::failed($document)) {
            return view('inspections.result', $document);
        }

        $verdict = $this->ai->reconcile($document['raw'], $vision['raw']);
        if (CrossInspectClient::failed($verdict)) {
            return view('inspections.result', $verdict);
        }

        return view('inspections.result', [
            'verdict' => $verdict,
            'document' => $document['data'],
            'vision' => $vision['data'],
            'documentName' => $documentName,
            'photoName' => $photoName,
            'isDemo' => true,
        ]);
    }

    /** @return array{0: string, 1: string} isi berkas dan namanya */
    private function sample(string $relative): array
    {
        $path = resource_path($relative);

        return [file_get_contents($path), basename($path)];
    }
}
