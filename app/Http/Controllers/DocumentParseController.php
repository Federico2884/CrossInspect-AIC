<?php

namespace App\Http\Controllers;

use App\Jobs\ParseDocument;
use App\Models\Document;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;

/**
 * Antarmuka Modul 1 (Document Parsing).
 *
 * Unggahan tidak dibaca di dalam request: berkas disimpan, satu baris dicatat,
 * pekerjaannya diantrekan, lalu halaman hasil menanyakan statusnya berkala.
 * Dengan engine asli satu halaman padat memakan menit, jadi request sinkron
 * berarti browser menggantung.
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

    public function parse(Request $request): RedirectResponse
    {
        $validated = $request->validate([
            // Batas 20 MB disamakan dengan service AI supaya penolakan terjadi
            // di sini, bukan setelah berkas terlanjur dikirim lewat jaringan.
            'file' => ['required', 'file', 'mimes:pdf,png,jpg,jpeg', 'max:20480'],
            'scenario' => ['nullable', 'string', 'in:'.implode(',', self::SCENARIOS)],
        ]);

        // Disimpan ke disk, bukan disimpan di memori: worker membacanya setelah
        // request ini sudah lama selesai.
        $path = $validated['file']->store('documents', 'local');

        $document = Document::create([
            'original_filename' => $validated['file']->getClientOriginalName(),
            'stored_path' => $path,
            'scenario' => $validated['scenario'] ?? null,
            'status' => Document::STATUS_QUEUED,
        ]);

        ParseDocument::dispatch($document);

        return redirect()->route('documents.show', $document);
    }

    public function show(Document $document): View
    {
        return view('documents.show', ['document' => $document]);
    }

    /**
     * Dipanggil berkala oleh halaman tunggu. Sengaja ringan.
     */
    public function status(Document $document): JsonResponse
    {
        return response()->json([
            'status' => $document->status,
            'pending' => $document->isPending(),
            'elapsed' => $document->elapsedSeconds(),
            'items' => $document->itemCount(),
        ]);
    }

    public function index(): View
    {
        return view('documents.index', [
            'documents' => Document::latest()->paginate(20),
        ]);
    }
}
