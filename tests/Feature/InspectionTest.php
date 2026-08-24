<?php

namespace Tests\Feature;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Request;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

/**
 * Alur utama cross-check. Seluruh test memalsukan service AI, jadi tidak ada
 * container, model, maupun jaringan yang dibutuhkan untuk menjalankannya.
 */
class InspectionTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        // Test tidak boleh bergantung pada hasil `npm run build`.
        $this->withoutVite();
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

    private function submit(array $overrides = [])
    {
        return $this->post('/inspections', array_merge([
            // create() alih-alih image(): image() butuh ekstensi GD, dan test ini
            // tidak sedang menguji isi gambar — hanya alurnya.
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
        // Kendali skenario tinggal di /demo. Memisahkannya menjaga muka aplikasi
        // menampilkan alur sungguhan saja — dan menghindarkan aturan "berkas
        // wajib kecuali kalau..." yang membingungkan di formulir ini.
        $this->get('/')
            ->assertDontSee('mixed_units')
            ->assertDontSee('partial_occlusion')
            ->assertSee(route('demo.create'), false);
    }

    public function test_a_matching_shipment_is_reported_as_matching(): void
    {
        $this->fakeAllThree();

        $this->submit()
            ->assertOk()
            ->assertSee('Cocok')
            ->assertSee('Susu UHT Ultra 250ml');
    }

    public function test_the_photo_is_inspected_before_the_document(): void
    {
        // Vision menjawab dalam milidetik, dokumen bisa memakan menit. Kalau
        // urutannya terbalik, foto yang ditolak baru ketahuan setelah pengguna
        // menunggu inference yang sia-sia.
        $this->fakeAllThree();
        $this->submit();

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

        $this->submit()
            ->assertOk()
            ->assertSee('Gambar tidak bisa didekode.')
            ->assertSee('UNREADABLE_IMAGE');

        Http::assertNotSent(fn (Request $request) => str_contains($request->url(), '/document/parse'));
    }

    public function test_unverified_parameters_are_never_shown_as_safe(): void
    {
        // Inti kejujuran sistem ini: petugas gudang tidak boleh membaca
        // "belum diperiksa" sebagai jaminan bahwa kemasan aman.
        $this->fakeAllThree();

        $response = $this->submit()->assertOk();

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

        $this->submit()
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

        $this->submit()->assertOk()->assertSee('Ada selisih')->assertSee('-2');
    }

    public function test_an_unreachable_service_explains_itself(): void
    {
        Http::fake(fn () => throw new ConnectionException('Connection refused'));

        $this->submit()
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

        $this->submit()->assertOk()->assertSee('Body gagal validasi.');
    }

    public function test_both_files_are_required(): void
    {
        $this->post('/inspections', [])->assertSessionHasErrors(['document', 'photo']);
    }

    public function test_a_pdf_is_not_accepted_as_the_goods_photo(): void
    {
        // Modul 2 menolak PDF; menangkapnya di sini menghemat satu perjalanan.
        $this->submit(['photo' => UploadedFile::fake()->create('bukan-foto.pdf', 12, 'application/pdf')])
            ->assertSessionHasErrors('photo');

        Http::assertNothingSent();
    }

    public function test_an_empty_detection_map_survives_the_round_trip(): void
    {
        // PHP tidak bisa membedakan map kosong dari list kosong: keduanya
        // menjadi array(). Kalau respons Modul 2 di-decode lalu di-encode ulang,
        // `class_counts: {}` berubah jadi `[]` dan Modul 3 menolaknya dengan 422.
        //
        // Itu bukan kasus pinggiran — persis itu yang terjadi setiap kali foto
        // tidak memuat objek apa pun, yaitu saat vonisnya justru paling penting.
        $vision = $this->visionPayload(['detected_count' => 0, 'class_counts' => new \stdClass()]);

        Http::fake([
            '*/vision/inspect' => Http::response(
                json_encode($vision), 200, ['Content-Type' => 'application/json']
            ),
            '*/document/parse' => Http::response($this->documentPayload()),
            '*/crosscheck' => Http::response($this->verdictPayload()),
        ]);

        $this->submit()->assertOk();

        Http::assertSent(fn (Request $request) => ! str_contains($request->url(), '/crosscheck')
            || str_contains($request->body(), '"class_counts":{}'));
    }
}
