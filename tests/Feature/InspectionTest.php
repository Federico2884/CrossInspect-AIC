<?php

namespace Tests\Feature;

use App\Jobs\InspectShipment;
use App\Models\Inspection;
use App\Services\CrossInspectClient;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Request;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

/**
 * Alur utama cross-check (terantre). Seluruh test memalsukan service AI,
 * jadi tidak ada container, model, maupun jaringan yang dibutuhkan untuk menjalankannya.
 */
class InspectionTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        // Test tidak boleh bergantung pada hasil `npm run build`.
        $this->withoutVite();
        Storage::fake('local');
    }

    private function documentPayload(array $overrides = []): array
    {
        return array_merge([
            'document_type' => 'SURAT_JALAN',
            'document_number' => 'SJ/2026/08/00142',
            'document_date' => '2026-08-12',
            'sender' => 'PT Sinar Terang',
            'recipient' => 'Toko Maju',
            'page_count' => 1,
            'items' => [[
                'item_name' => 'Susu UHT Ultra 250ml',
                'sku' => 'ULT-250',
                'quantity' => 10,
                'unit_raw' => 'Karton',
                'unit_normalized' => 'karton',
                'quantity_per_unit' => 12,
                'total_pieces' => 120,
                'source_page' => 1,
            ]],
            'confidence' => ['document_number' => 0.93, 'items' => [0.95], 'overall' => 0.86],
            'warnings' => [],
            'meta' => ['engine' => 'mock', 'device' => 'cpu', 'processing_ms' => 3, 'scenario' => null, 'debug' => null],
        ], $overrides);
    }

    private function visionPayload(array $overrides = []): array
    {
        return array_merge([
            'detected_count' => 10,
            'class_counts' => ['cardboard' => 10],
            'detections' => [],
            'count_confidence' => ['mean_detection' => 0.86, 'min_detection' => 0.7, 'overall' => 0.86],
            'defect' => ['status' => 'unavailable', 'findings' => []],
            'warnings' => [],
            'meta' => [
                'engine' => 'mock', 'device' => 'cpu', 'processing_ms' => 12,
                'model' => null, 'conf_threshold' => 0.4,
                'image_width' => 1280, 'image_height' => 960, 'scenario' => null, 'debug' => null,
            ],
        ], $overrides);
    }

    private function verdictPayload(array $overrides = []): array
    {
        return array_merge([
            'status' => 'MATCH',
            'quantity' => [
                'document_total' => 10,
                'detected_total' => 10,
                'difference' => 0,
                'counted_items' => [[
                    'item_index' => 0, 'item_name' => 'Susu UHT Ultra 250ml',
                    'quantity' => 10, 'unit_raw' => 'Karton', 'unit_normalized' => 'karton',
                ]],
                'excluded_items' => [],
            ],
            'identity' => ['status' => 'unavailable', 'reason' => 'Model vision hanya mengenali satu kelas.'],
            'integrity' => ['status' => 'unavailable', 'reason' => 'Model kerusakan belum tersedia.'],
            'warnings' => [],
            'meta' => [
                'engine' => 'rules', 'device' => 'cpu', 'processing_ms' => 1,
                'document_engine' => 'mock', 'vision_engine' => 'mock', 'scenario' => null, 'debug' => null,
            ],
        ], $overrides);
    }

    private function fakeAllThree(array $verdict = []): void
    {
        Http::fake([
            '*/vision/inspect' => Http::response($this->visionPayload()),
            '*/document/parse' => Http::response($this->documentPayload()),
            '*/crosscheck' => Http::response($this->verdictPayload($verdict)),
        ]);
    }

    private function inspectionFor(array $attributes = []): Inspection
    {
        Storage::disk('local')->put('documents/sj.pdf', '%PDF-1.7');
        Storage::disk('local')->put('photos/tumpukan.jpg', 'fake-image-bytes');

        return Inspection::create(array_merge([
            'document_original_name' => 'sj.pdf',
            'document_stored_path' => 'documents/sj.pdf',
            'photo_original_name' => 'tumpukan.jpg',
            'photo_stored_path' => 'photos/tumpukan.jpg',
            'status' => Inspection::STATUS_QUEUED,
        ], $attributes));
    }

    private function submit(array $overrides = [])
    {
        return $this->post('/inspections', array_merge([
            'document' => UploadedFile::fake()->create('sj.pdf', 100, 'application/pdf'),
            'photo' => UploadedFile::fake()->create('tumpukan.jpg', 100, 'image/jpeg'),
        ], $overrides));
    }

    public function test_the_form_is_the_front_page(): void
    {
        $this->get('/')
            ->assertOk()
            ->assertSee('Periksa kiriman')
            ->assertSee('Surat Jalan')
            ->assertSee('Foto tumpukan barang');
    }

    public function test_the_front_page_carries_no_mock_controls(): void
    {
        $this->get('/')
            ->assertDontSee('mixed_units')
            ->assertDontSee('partial_occlusion')
            ->assertSee(route('demo.create'), false);
    }

    public function test_upload_stores_both_files_and_queues_inspect_job(): void
    {
        Queue::fake();

        $this->submit()->assertRedirect();

        $inspection = Inspection::sole();
        $this->assertSame('sj.pdf', $inspection->document_original_name);
        $this->assertSame('tumpukan.jpg', $inspection->photo_original_name);
        $this->assertTrue(Storage::disk('local')->exists($inspection->document_stored_path));
        $this->assertTrue(Storage::disk('local')->exists($inspection->photo_stored_path));

        Queue::assertPushed(InspectShipment::class, function (InspectShipment $job) use ($inspection) {
            return $job->inspection->id === $inspection->id;
        });
    }

    public function test_upload_redirects_to_the_waiting_page(): void
    {
        Queue::fake();

        $response = $this->submit();
        $inspection = Inspection::sole();

        $response->assertRedirect(route('inspections.show', $inspection));
    }

    public function test_both_files_are_required(): void
    {
        $this->post('/inspections', [])->assertSessionHasErrors(['document', 'photo']);
    }

    public function test_a_pdf_is_not_accepted_as_the_goods_photo(): void
    {
        $this->submit(['photo' => UploadedFile::fake()->create('bukan-foto.pdf', 12, 'application/pdf')])
            ->assertSessionHasErrors('photo');

        Http::assertNothingSent();
    }

    public function test_job_records_a_successful_crosscheck_matching(): void
    {
        $this->fakeAllThree();
        $inspection = $this->inspectionFor();

        (new InspectShipment($inspection))->handle(app(CrossInspectClient::class));

        $inspection->refresh();
        $this->assertTrue($inspection->isDone());
        $this->assertSame('MATCH', $inspection->verdict_response['status']);

        $this->get(route('inspections.show', $inspection))
            ->assertOk()
            ->assertSee('Cocok')
            ->assertSee('Susu UHT Ultra 250ml');
    }

    public function test_the_photo_is_inspected_before_the_document(): void
    {
        $this->fakeAllThree();
        $inspection = $this->inspectionFor();

        (new InspectShipment($inspection))->handle(app(CrossInspectClient::class));

        $paths = collect(Http::recorded())
            ->map(fn (array $pair) => parse_url($pair[0]->url(), PHP_URL_PATH))
            ->all();

        $this->assertSame(['/vision/inspect', '/document/parse', '/crosscheck'], $paths);
    }

    public function test_a_rejected_photo_never_costs_a_document_inference(): void
    {
        Http::fake([
            '*/vision/inspect' => Http::response(
                ['error' => ['code' => 'UNREADABLE_IMAGE', 'message' => 'Gambar tidak bisa didekode.', 'detail' => null]],
                422
            ),
            '*/document/parse' => Http::response($this->documentPayload()),
            '*/crosscheck' => Http::response($this->verdictPayload()),
        ]);

        $inspection = $this->inspectionFor();
        (new InspectShipment($inspection))->handle(app(CrossInspectClient::class));

        $inspection->refresh();
        $this->assertTrue($inspection->hasFailed());
        $this->assertSame('Gambar tidak bisa didekode.', $inspection->error['failure']);

        $this->get(route('inspections.show', $inspection))
            ->assertOk()
            ->assertSee('Gambar tidak bisa didekode.')
            ->assertSee('UNREADABLE_IMAGE');

        Http::assertNotSent(fn (Request $request) => str_contains($request->url(), '/document/parse'));
    }

    public function test_unverified_parameters_are_never_shown_as_safe(): void
    {
        $this->fakeAllThree();
        $inspection = $this->inspectionFor();
        (new InspectShipment($inspection))->handle(app(CrossInspectClient::class));

        $response = $this->get(route('inspections.show', $inspection))->assertOk();

        $response->assertSee('Belum diperiksa');
        $response->assertSee('Identitas produk');
        $response->assertSee('Integritas fisik');
        $response->assertDontSee('Kemasan aman');
    }

    public function test_excluded_rows_are_shown_with_their_reason(): void
    {
        $this->fakeAllThree([
            'status' => 'PARTIAL',
            'quantity' => [
                'document_total' => 10,
                'detected_total' => 10,
                'difference' => 0,
                'counted_items' => [[
                    'item_index' => 0, 'item_name' => 'Susu UHT Ultra 250ml',
                    'quantity' => 10, 'unit_raw' => 'Karton', 'unit_normalized' => 'karton',
                ]],
                'excluded_items' => [[
                    'item_index' => 1, 'item_name' => 'Gula Pasir',
                    'quantity' => 50, 'unit_raw' => 'Kg', 'unit_normalized' => 'kg',
                    'reason' => 'UNIT_IS_WEIGHT',
                ]],
            ],
        ]);

        $inspection = $this->inspectionFor();
        (new InspectShipment($inspection))->handle(app(CrossInspectClient::class));

        $this->get(route('inspections.show', $inspection))
            ->assertOk()
            ->assertSee('Cocok sebagian')
            ->assertSee('Gula Pasir')
            ->assertSee('satuan berat');
    }

    public function test_a_shortfall_is_reported_as_a_difference(): void
    {
        $this->fakeAllThree([
            'status' => 'MISMATCH',
            'quantity' => [
                'document_total' => 10, 'detected_total' => 8, 'difference' => -2,
                'counted_items' => [], 'excluded_items' => [],
            ],
        ]);

        $inspection = $this->inspectionFor();
        (new InspectShipment($inspection))->handle(app(CrossInspectClient::class));

        $this->get(route('inspections.show', $inspection))
            ->assertOk()
            ->assertSee('Ada selisih')
            ->assertSee('-2');
    }

    public function test_an_unreachable_service_explains_itself(): void
    {
        Http::fake(fn () => throw new ConnectionException('Connection refused'));

        $inspection = $this->inspectionFor();
        (new InspectShipment($inspection))->handle(app(CrossInspectClient::class));

        $inspection->refresh();
        $this->assertTrue($inspection->hasFailed());

        $this->get(route('inspections.show', $inspection))
            ->assertOk()
            ->assertSee('Tidak bisa menghubungi service AI')
            ->assertSee('memeriksa foto barang');
    }

    public function test_a_failing_crosscheck_surfaces_its_error(): void
    {
        Http::fake([
            '*/vision/inspect' => Http::response($this->visionPayload()),
            '*/document/parse' => Http::response($this->documentPayload()),
            '*/crosscheck' => Http::response(
                ['error' => ['code' => 'INVALID_REQUEST', 'message' => 'Body gagal validasi.', 'detail' => null]],
                422
            ),
        ]);

        $inspection = $this->inspectionFor();
        (new InspectShipment($inspection))->handle(app(CrossInspectClient::class));

        $inspection->refresh();
        $this->assertTrue($inspection->hasFailed());

        $this->get(route('inspections.show', $inspection))
            ->assertOk()
            ->assertSee('Body gagal validasi.');
    }

    public function test_waiting_page_shows_while_job_is_pending(): void
    {
        $inspection = $this->inspectionFor(['status' => Inspection::STATUS_PROCESSING_DOCUMENT]);

        $this->get(route('inspections.show', $inspection))
            ->assertOk()
            ->assertSee('Membaca dokumen')
            ->assertSee('id="pending"', false);
    }

    public function test_status_endpoint_reports_each_state(): void
    {
        $inspection = $this->inspectionFor(['status' => Inspection::STATUS_PROCESSING_VISION]);

        $this->get(route('inspections.status', $inspection))
            ->assertOk()
            ->assertJson([
                'status' => 'processing_vision',
                'pending' => true,
            ]);
    }

    public function test_an_empty_detection_map_survives_the_round_trip(): void
    {
        $vision = $this->visionPayload(['detected_count' => 0, 'class_counts' => new \stdClass()]);

        Http::fake([
            '*/vision/inspect' => Http::response(
                json_encode($vision), 200, ['Content-Type' => 'application/json']
            ),
            '*/document/parse' => Http::response($this->documentPayload()),
            '*/crosscheck' => Http::response($this->verdictPayload()),
        ]);

        $inspection = $this->inspectionFor();
        (new InspectShipment($inspection))->handle(app(CrossInspectClient::class));

        Http::assertSent(fn (Request $request) => ! str_contains($request->url(), '/crosscheck')
            || str_contains($request->body(), '"class_counts":{}'));
    }

    public function test_inspection_result_shows_document_metadata(): void
    {
        $this->fakeAllThree();
        $inspection = $this->inspectionFor();
        (new InspectShipment($inspection))->handle(app(CrossInspectClient::class));

        $this->get(route('inspections.show', $inspection))
            ->assertOk()
            ->assertSee('SJ/2026/08/00142')
            ->assertSee('PT Sinar Terang')
            ->assertSee('Toko Maju')
            ->assertSee('2026-08-12')
            ->assertSee('SURAT_JALAN');
    }

    public function test_history_lists_past_inspections(): void
    {
        $inspection = $this->inspectionFor([
            'status' => Inspection::STATUS_DONE,
            'document_response' => ['data' => $this->documentPayload()],
            'verdict_response' => $this->verdictPayload(),
        ]);

        $this->get(route('inspections.index'))
            ->assertOk()
            ->assertSee('Riwayat pemeriksaan')
            ->assertSee('SJ/2026/08/00142')
            ->assertSee('Cocok');
    }

    public function test_history_url_is_not_swallowed_by_the_id_wildcard(): void
    {
        $this->get('/inspections/riwayat')
            ->assertOk()
            ->assertDontSee('Pemeriksaan gagal')
            ->assertSee('Riwayat pemeriksaan');
    }

    public function test_history_is_empty_without_crashing(): void
    {
        $this->get('/inspections/riwayat')
            ->assertOk()
            ->assertSee('Belum ada pemeriksaan kiriman');
    }
}
