<?php

namespace Tests\Feature;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

/**
 * Antarmuka uji Modul 1. Seluruh test memalsukan service AI, jadi tidak ada
 * container, model, maupun jaringan yang dibutuhkan untuk menjalankannya.
 */
class DocumentParseTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        // Test tidak boleh bergantung pada hasil `npm run build`. Tanpa ini,
        // suite gagal di mesin yang belum pernah membangun aset — kegagalan
        // yang tidak ada hubungannya dengan logika yang sedang diuji.
        $this->withoutVite();
    }

    private function successPayload(array $overrides = []): array
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
            'meta' => [
                'engine' => 'mock',
                'device' => 'cpu',
                'processing_ms' => 3,
                'scenario' => 'clean_surat_jalan',
                'debug' => null,
            ],
        ], $overrides);
    }

    public function test_upload_form_lists_the_mock_scenarios(): void
    {
        $this->get('/documents')
            ->assertOk()
            ->assertSee('Baca Surat Jalan', false)
            ->assertSee('mixed_units')
            ->assertSee('low_confidence');
    }

    public function test_successful_parse_renders_the_contract_fields(): void
    {
        Http::fake(['*/document/parse' => Http::response($this->successPayload(), 200)]);

        $this->post('/documents/parse', ['file' => UploadedFile::fake()->create('sj.pdf', 100, 'application/pdf')])
            ->assertOk()
            ->assertSee('SJ/2026/08/00142')
            ->assertSee('Susu UHT Ultra 250ml')
            ->assertSee('Karton')
            ->assertSee('120');
    }

    public function test_warnings_are_shown_with_their_code(): void
    {
        Http::fake(['*/document/parse' => Http::response($this->successPayload([
            'warnings' => [[
                'code' => 'AMBIGUOUS_UNIT',
                'message' => 'Satuan Ball di luar daftar normalisasi.',
                'severity' => 'warning',
                'item_index' => 0,
            ]],
        ]), 200)]);

        $this->post('/documents/parse', ['file' => UploadedFile::fake()->create('sj.pdf', 100, 'application/pdf')])
            ->assertOk()
            ->assertSee('AMBIGUOUS_UNIT')
            ->assertSee('Satuan Ball di luar daftar normalisasi.');
    }

    public function test_error_envelope_is_rendered_instead_of_a_stack_trace(): void
    {
        Http::fake(['*/document/parse' => Http::response([
            'error' => [
                'code' => 'FILE_TOO_LARGE',
                'message' => 'File exceeds the 20 MB limit.',
                'detail' => 'received 21000000 bytes',
            ],
        ], 413)]);

        $this->post('/documents/parse', ['file' => UploadedFile::fake()->create('sj.pdf', 100, 'application/pdf')])
            ->assertOk()
            ->assertSee('File exceeds the 20 MB limit.')
            ->assertSee('FILE_TOO_LARGE');
    }

    public function test_unreachable_service_shows_a_readable_message(): void
    {
        Http::fake(fn () => throw new ConnectionException('Connection refused'));

        $this->post('/documents/parse', ['file' => UploadedFile::fake()->create('sj.pdf', 100, 'application/pdf')])
            ->assertOk()
            ->assertSee('Tidak bisa menghubungi service AI', false);
    }

    public function test_rejects_a_file_type_the_service_cannot_read(): void
    {
        Http::fake();

        $this->post('/documents/parse', ['file' => UploadedFile::fake()->create('notes.txt', 10, 'text/plain')])
            ->assertSessionHasErrors('file');

        Http::assertNothingSent();
    }

    public function test_rejects_a_file_over_the_twenty_megabyte_cap(): void
    {
        Http::fake();

        $this->post('/documents/parse', ['file' => UploadedFile::fake()->create('big.pdf', 20481, 'application/pdf')])
            ->assertSessionHasErrors('file');

        Http::assertNothingSent();
    }

    public function test_scenario_is_forwarded_to_the_service(): void
    {
        Http::fake(['*/document/parse' => Http::response($this->successPayload(), 200)]);

        $this->post('/documents/parse', [
            'file' => UploadedFile::fake()->create('sj.pdf', 100, 'application/pdf'),
            'scenario' => 'mixed_units',
        ])->assertOk();

        Http::assertSent(function ($request) {
            $names = collect($request->data())->pluck('name');

            return str_contains($request->url(), '/document/parse')
                && $names->contains('file')
                && $names->contains('scenario');
        });
    }

    public function test_unknown_scenario_is_rejected_before_calling_the_service(): void
    {
        Http::fake();

        $this->post('/documents/parse', [
            'file' => UploadedFile::fake()->create('sj.pdf', 100, 'application/pdf'),
            'scenario' => 'tidak_ada',
        ])->assertSessionHasErrors('scenario');

        Http::assertNothingSent();
    }
}
