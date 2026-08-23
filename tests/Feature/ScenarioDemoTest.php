<?php

namespace Tests\Feature;

use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

/**
 * Halaman uji skenario.
 *
 * Yang dijaga di sini bukan sekadar "halamannya jalan", melainkan dua janji
 * yang membuat halaman ini boleh ada: ia tidak pernah menuntut unggahan, dan
 * hasilnya tidak pernah bisa disangka pemeriksaan sungguhan.
 */
class ScenarioDemoTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        $this->withoutVite();
    }

    private function fakeAllThree(): void
    {
        Http::fake([
            '*/vision/inspect' => Http::response([
                'detected_count' => 10,
                'class_counts' => ['cardboard' => 10],
                'detections' => [],
                'count_confidence' => ['mean_detection' => 0.86, 'min_detection' => 0.7, 'overall' => 0.86],
                'defect' => ['status' => 'unavailable', 'findings' => []],
                'warnings' => [],
                'meta' => [
                    'engine' => 'mock', 'device' => 'cpu', 'processing_ms' => 12,
                    'model' => null, 'conf_threshold' => 0.4,
                    'image_width' => 1280, 'image_height' => 960,
                    'scenario' => 'partial_occlusion', 'debug' => null,
                ],
            ]),
            '*/document/parse' => Http::response([
                'document_type' => 'SURAT_JALAN',
                'document_number' => 'SJ/2026/08/00142',
                'document_date' => '2026-08-12',
                'sender' => 'PT Sinar Terang',
                'recipient' => 'Toko Maju',
                'page_count' => 1,
                'items' => [],
                'confidence' => ['document_number' => 0.93, 'items' => [], 'overall' => 0.86],
                'warnings' => [],
                'meta' => [
                    'engine' => 'mock', 'device' => 'cpu', 'processing_ms' => 3,
                    'scenario' => 'mixed_units', 'debug' => null,
                ],
            ]),
            '*/crosscheck' => Http::response([
                'status' => 'MATCH',
                'quantity' => [
                    'document_total' => 10, 'detected_total' => 10, 'difference' => 0,
                    'counted_items' => [], 'excluded_items' => [],
                ],
                'identity' => ['status' => 'unavailable', 'reason' => 'Model satu kelas.'],
                'integrity' => ['status' => 'unavailable', 'reason' => 'Model kerusakan belum ada.'],
                'warnings' => [],
                'meta' => [
                    'engine' => 'rules', 'device' => 'cpu', 'processing_ms' => 1,
                    'document_engine' => 'mock', 'vision_engine' => 'mock',
                    'scenario' => null, 'debug' => null,
                ],
            ]),
        ]);
    }

    public function test_the_page_offers_scenarios_for_both_modules(): void
    {
        $this->get('/demo')
            ->assertOk()
            ->assertSee('mixed_units')        // skenario dokumen
            ->assertSee('partial_occlusion'); // skenario vision
    }

    public function test_a_scenario_runs_without_any_upload(): void
    {
        // Inti keberadaan halaman ini: satu klik, tanpa menyiapkan berkas.
        $this->fakeAllThree();

        $this->post('/demo', [
            'document_scenario' => 'mixed_units',
            'vision_scenario' => 'partial_occlusion',
        ])->assertOk()->assertSee('Hasil pemeriksaan');
    }

    public function test_the_bundled_samples_are_really_sent_to_the_service(): void
    {
        // Berkas contoh dikirim sungguhan, bukan diakali dengan melewati
        // service — kalau tidak, demo menempuh jalur kode yang berbeda dari
        // produksi dan berhenti membuktikan apa pun.
        $this->fakeAllThree();

        $this->post('/demo', ['vision_scenario' => 'clean_stack']);

        Http::assertSent(function (Request $request) {
            if (! str_contains($request->url(), '/vision/inspect')) {
                return false;
            }
            $names = array_column($request->data(), 'name');

            return in_array('file', $names, true);
        });
    }

    public function test_the_result_is_marked_as_a_demo(): void
    {
        // Tanpa penanda ini, keluaran fixture terlihat sama persis dengan
        // pemeriksaan sungguhan.
        $this->fakeAllThree();

        $this->post('/demo', ['document_scenario' => 'clean_surat_jalan'])
            ->assertSee('skenario contoh');
    }

    public function test_an_unknown_scenario_is_rejected(): void
    {
        // Salah ketik harus terlihat, bukan diam-diam jatuh ke default.
        $this->post('/demo', ['document_scenario' => 'tidak_ada'])
            ->assertSessionHasErrors('document_scenario');
    }

    public function test_scenarios_are_optional(): void
    {
        $this->fakeAllThree();

        $this->post('/demo')->assertOk();
    }
}
