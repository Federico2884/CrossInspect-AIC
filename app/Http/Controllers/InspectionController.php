<?php

namespace App\Http\Controllers;

use App\Services\CrossInspectClient;
use Illuminate\Http\Request;
use Illuminate\View\View;

/**
 * Alur utama CrossInspect: satu dokumen, satu foto, satu vonis.
 *
 * Halaman ini memanggil tiga endpoint service AI secara berurutan dalam satu
 * request. Urutannya disengaja — vision lebih dulu karena ia menjawab dalam
 * milidetik, jadi service yang mati atau berkas yang ditolak ketahuan sebelum
 * pengguna menunggu inference dokumen yang bisa memakan menit.
 *
 * Halaman ini sengaja tidak punya kendali skenario mock. Alat uji itu tinggal
 * di ScenarioDemoController, supaya muka aplikasi menampilkan alur sungguhan
 * saja — dan supaya aturan "berkas wajib" di sini tidak perlu dilonggarkan demi
 * kenyamanan mencoba.
 *
 * JSON dari service diteruskan apa adanya ke view. Memetakannya ke objek PHP
 * hanya menciptakan tempat kedua yang bisa menyimpang dari kontrak di
 * ai/app/modules/.
 */
class InspectionController extends Controller
{
    public function __construct(private readonly CrossInspectClient $ai) {}

    public function create(): View
    {
        return view('inspections.create');
    }

    public function inspect(Request $request): View
    {
        $validated = $request->validate([
            // Batas 20 MB disamakan dengan service AI supaya penolakan terjadi
            // di sini, bukan setelah berkas terlanjur dikirim lewat jaringan.
            'document' => ['required', 'file', 'mimes:pdf,png,jpg,jpeg', 'max:20480'],
            // Modul 2 menolak PDF dan menerima WebP — berbeda dari Modul 1.
            'photo' => ['required', 'file', 'mimes:png,jpg,jpeg,webp', 'max:20480'],
        ]);

        $photo = $validated['photo'];
        $vision = $this->ai->upload(
            '/vision/inspect',
            file_get_contents($photo->getRealPath()),
            $photo->getClientOriginalName(),
            null,
            'memeriksa foto barang'
        );
        if (CrossInspectClient::failed($vision)) {
            return view('inspections.result', $vision);
        }

        $document = $validated['document'];
        $parsed = $this->ai->upload(
            '/document/parse',
            file_get_contents($document->getRealPath()),
            $document->getClientOriginalName(),
            null,
            'membaca dokumen'
        );
        if (CrossInspectClient::failed($parsed)) {
            return view('inspections.result', $parsed);
        }

        $verdict = $this->ai->reconcile($parsed['raw'], $vision['raw']);
        if (CrossInspectClient::failed($verdict)) {
            return view('inspections.result', $verdict);
        }

        return view('inspections.result', [
            'verdict' => $verdict,
            'document' => $parsed['data'],
            'vision' => $vision['data'],
            'documentName' => $document->getClientOriginalName(),
            'photoName' => $photo->getClientOriginalName(),
        ]);
    }
}
