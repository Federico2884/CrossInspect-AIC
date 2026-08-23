<?php

namespace Tests\Feature;

use App\Jobs\ParseDocument;
use App\Models\Document;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

/**
 * Antarmuka Modul 1. Seluruh test memalsukan service AI, jadi tidak ada
 * container, model, maupun jaringan yang dibutuhkan untuk menjalankannya.
 */
class DocumentParseTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        // Test tidak boleh bergantung pada hasil `npm run build`.
        $this->withoutVite();
        Storage::fake('local');
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

    private function pdf(): UploadedFile
    {
        return UploadedFile::fake()->create('sj.pdf', 100, 'application/pdf');
    }

    private function documentFor(array $attributes = []): Document
    {
        Storage::disk('local')->put('documents/sj.pdf', '%PDF-1.7');

        return Document::create(array_merge([
            'original_filename' => 'sj.pdf',
            'stored_path' => 'documents/sj.pdf',
            'status' => Document::STATUS_QUEUED,
        ], $attributes));
    }

    // ----------------------------------------------------------------------
    // Unggahan
    // ----------------------------------------------------------------------

    public function test_upload_form_lists_the_mock_scenarios(): void
    {
        $this->get('/documents')
            ->assertOk()
            ->assertSee('Baca Surat Jalan', false)
            ->assertSee('mixed_units')
            ->assertSee('low_confidence');
    }

    public function test_upload_stores_the_file_and_queues_exactly_one_job(): void
    {
        Queue::fake();

        $this->post('/documents/parse', ['file' => $this->pdf(), 'scenario' => 'mixed_units'])
            ->assertRedirect();

        $document = Document::sole();
        $this->assertSame('sj.pdf', $document->original_filename);
        $this->assertSame('mixed_units', $document->scenario);
        $this->assertSame(Document::STATUS_QUEUED, $document->status);
        Storage::disk('local')->assertExists($document->stored_path);

        Queue::assertPushed(ParseDocument::class, 1);
    }

    public function test_upload_redirects_to_the_waiting_page(): void
    {
        Queue::fake();

        $response = $this->post('/documents/parse', ['file' => $this->pdf()]);

        $response->assertRedirect(route('documents.show', Document::sole()));
    }

    public function test_rejects_a_file_type_the_service_cannot_read(): void
    {
        Queue::fake();

        $this->post('/documents/parse', [
            'file' => UploadedFile::fake()->create('notes.txt', 10, 'text/plain'),
        ])->assertSessionHasErrors('file');

        Queue::assertNothingPushed();
        $this->assertSame(0, Document::count());
    }

    public function test_rejects_a_file_over_the_twenty_megabyte_cap(): void
    {
        Queue::fake();

        $this->post('/documents/parse', [
            'file' => UploadedFile::fake()->create('big.pdf', 20481, 'application/pdf'),
        ])->assertSessionHasErrors('file');

        Queue::assertNothingPushed();
    }

    public function test_unknown_scenario_is_rejected_before_queueing(): void
    {
        Queue::fake();

        $this->post('/documents/parse', ['file' => $this->pdf(), 'scenario' => 'tidak_ada'])
            ->assertSessionHasErrors('scenario');

        Queue::assertNothingPushed();
    }

    // ----------------------------------------------------------------------
    // Job
    // ----------------------------------------------------------------------

    public function test_job_records_a_successful_parse(): void
    {
        Http::fake(['*/document/parse' => Http::response($this->successPayload(), 200)]);
        $document = $this->documentFor();

        (new ParseDocument($document))->handle();

        $document->refresh();
        $this->assertSame(Document::STATUS_DONE, $document->status);
        $this->assertSame('SJ/2026/08/00142', $document->response['document_number']);
        $this->assertNotNull($document->finished_at);
        $this->assertNull($document->error);
    }

    public function test_job_forwards_the_scenario_to_the_service(): void
    {
        Http::fake(['*/document/parse' => Http::response($this->successPayload(), 200)]);

        (new ParseDocument($this->documentFor(['scenario' => 'mixed_units'])))->handle();

        Http::assertSent(function ($request) {
            $names = collect($request->data())->pluck('name');

            return str_contains($request->url(), '/document/parse')
                && $names->contains('file')
                && $names->contains('scenario');
        });
    }

    public function test_job_records_the_error_envelope_rather_than_throwing(): void
    {
        Http::fake(['*/document/parse' => Http::response([
            'error' => [
                'code' => 'FILE_TOO_LARGE',
                'message' => 'File exceeds the 20 MB limit.',
                'detail' => 'received 21000000 bytes',
            ],
        ], 413)]);
        $document = $this->documentFor();

        (new ParseDocument($document))->handle();

        $document->refresh();
        $this->assertSame(Document::STATUS_FAILED, $document->status);
        $this->assertSame('FILE_TOO_LARGE', $document->error['code']);
    }

    public function test_job_marks_failed_when_the_service_is_unreachable(): void
    {
        Http::fake(fn () => throw new ConnectionException('Connection refused'));
        $document = $this->documentFor();

        (new ParseDocument($document))->handle();

        $document->refresh();
        $this->assertSame(Document::STATUS_FAILED, $document->status);
        $this->assertSame('SERVICE_UNREACHABLE', $document->error['code']);
    }

    public function test_job_timeout_stays_below_the_queue_retry_window(): void
    {
        /**
         * Kalau retry_after lebih kecil dari timeout job, antrean menyerahkan
         * job yang masih menunggu model ke worker kedua — dokumen yang sama
         * dibaca dua kali. Mahal, dan sulit disadari.
         */
        $job = new ParseDocument($this->documentFor());

        $this->assertLessThan(config('queue.connections.database.retry_after'), $job->timeout);
    }

    // ----------------------------------------------------------------------
    // Halaman hasil & status
    // ----------------------------------------------------------------------

    public function test_waiting_page_shows_while_the_job_is_pending(): void
    {
        $this->get(route('documents.show', $this->documentFor()))
            ->assertOk()
            ->assertSee('antrean', false)
            ->assertSee('queue:work', false);
    }

    public function test_finished_page_renders_the_contract_fields(): void
    {
        $document = $this->documentFor([
            'status' => Document::STATUS_DONE,
            'response' => $this->successPayload(),
        ]);

        $this->get(route('documents.show', $document))
            ->assertOk()
            ->assertSee('SJ/2026/08/00142')
            ->assertSee('Susu UHT Ultra 250ml')
            ->assertSee('Karton')
            ->assertSee('120');
    }

    public function test_finished_page_shows_warnings_with_their_code(): void
    {
        $document = $this->documentFor([
            'status' => Document::STATUS_DONE,
            'response' => $this->successPayload([
                'warnings' => [[
                    'code' => 'AMBIGUOUS_UNIT',
                    'message' => 'Satuan Ball di luar daftar normalisasi.',
                    'severity' => 'warning',
                    'item_index' => 0,
                ]],
            ]),
        ]);

        $this->get(route('documents.show', $document))
            ->assertOk()
            ->assertSee('AMBIGUOUS_UNIT')
            ->assertSee('Satuan Ball di luar daftar normalisasi.');
    }

    public function test_failed_page_shows_the_reason_not_a_stack_trace(): void
    {
        $document = $this->documentFor([
            'status' => Document::STATUS_FAILED,
            'error' => ['code' => 'SERVICE_UNREACHABLE', 'message' => 'Tidak bisa menghubungi service AI.'],
        ]);

        $this->get(route('documents.show', $document))
            ->assertOk()
            ->assertSee('Tidak bisa menghubungi service AI.')
            ->assertSee('SERVICE_UNREACHABLE');
    }

    public function test_status_endpoint_reports_each_state(): void
    {
        $pending = $this->documentFor();
        $this->getJson(route('documents.status', $pending))
            ->assertOk()
            ->assertJson(['status' => 'queued', 'pending' => true, 'items' => null]);

        $done = $this->documentFor([
            'status' => Document::STATUS_DONE,
            'response' => $this->successPayload(),
        ]);
        $this->getJson(route('documents.status', $done))
            ->assertOk()
            ->assertJson(['status' => 'done', 'pending' => false, 'items' => 1]);
    }

    // ----------------------------------------------------------------------
    // Riwayat
    // ----------------------------------------------------------------------

    public function test_history_lists_past_parses(): void
    {
        $this->documentFor([
            'status' => Document::STATUS_DONE,
            'response' => $this->successPayload(),
        ]);

        $this->get(route('documents.index'))
            ->assertOk()
            ->assertSee('sj.pdf')
            ->assertSee('selesai');
    }

    public function test_history_url_is_not_swallowed_by_the_id_wildcard(): void
    {
        /**
         * '/documents/riwayat' harus mencapai halaman riwayat, bukan dicari
         * sebagai record dengan id 'riwayat'.
         */
        $this->get('/documents/riwayat')->assertOk();
    }

    public function test_history_is_empty_without_crashing(): void
    {
        $this->get(route('documents.index'))
            ->assertOk()
            ->assertSee('Belum ada dokumen yang dibaca.');
    }
}
