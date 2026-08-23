<?php

namespace App\Http\Controllers;

use App\Jobs\InspectShipment;
use App\Models\Inspection;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;

/**
 * Alur utama CrossInspect: satu dokumen, satu foto, satu vonis.
 *
 * Unggahan disimpan ke storage server dan pekerjaan diantrekan (InspectShipment),
 * lalu browser diarahkan ke halaman tunggu yang melakukan polling status berkala.
 */
class InspectionController extends Controller
{
    public function index(): View
    {
        return view('inspections.index', [
            'inspections' => Inspection::latest()->paginate(20),
        ]);
    }

    public function create(): View
    {
        return view('inspections.create');
    }

    public function inspect(Request $request): RedirectResponse
    {
        $validated = $request->validate([
            // Batas 20 MB disamakan dengan service AI supaya penolakan terjadi
            // di sini, bukan setelah berkas terlanjur dikirim lewat jaringan.
            'document' => ['required', 'file', 'mimes:pdf,png,jpg,jpeg', 'max:20480'],
            // Modul 2 menolak PDF dan menerima WebP — berbeda dari Modul 1.
            'photo' => ['required', 'file', 'mimes:png,jpg,jpeg,webp', 'max:20480'],
        ]);

        $documentPath = $validated['document']->store('documents', 'local');
        $photoPath = $validated['photo']->store('photos', 'local');

        $inspection = Inspection::create([
            'document_original_name' => $validated['document']->getClientOriginalName(),
            'document_stored_path' => $documentPath,
            'photo_original_name' => $validated['photo']->getClientOriginalName(),
            'photo_stored_path' => $photoPath,
            'status' => Inspection::STATUS_QUEUED,
        ]);

        InspectShipment::dispatch($inspection);

        return redirect()->route('inspections.show', $inspection);
    }

    public function show(Inspection $inspection): View
    {
        return view('inspections.show', ['inspection' => $inspection]);
    }

    /**
     * Dipanggil berkala oleh JavaScript halaman tunggu.
     */
    public function status(Inspection $inspection): JsonResponse
    {
        return response()->json([
            'status' => $inspection->status,
            'pending' => $inspection->isPending(),
            'elapsed' => $inspection->elapsedSeconds(),
            'step' => $inspection->stepLabel(),
        ]);
    }
}
