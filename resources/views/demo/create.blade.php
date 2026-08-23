@extends('layouts.app')

@section('title', 'Uji Skenario')
@section('heading', 'Uji skenario')
@section('subheading', 'Peragakan alur cross-check tanpa menyiapkan berkas apa pun.')

@section('content')
    <div class="mb-6 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
        Halaman ini memakai <strong>berkas contoh bawaan</strong> dan engine mock, jadi hasilnya
        fixture — bukan pembacaan sungguhan. Untuk memeriksa kiriman nyata, pakai
        <a href="{{ route('inspections.create') }}" class="underline hover:text-sky-950">halaman utama</a>.
    </div>

    <form method="POST"
          action="{{ route('demo.run') }}"
          id="demo-form"
          class="space-y-6 rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
        @csrf

        <div class="grid gap-6 sm:grid-cols-2">
            <div>
                <label for="document_scenario" class="block text-sm font-medium text-neutral-800">
                    Skenario dokumen
                </label>
                <select name="document_scenario"
                        id="document_scenario"
                        class="mt-2 block w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm">
                    <option value="">Otomatis — dari hash isi berkas</option>
                    @foreach ($documentScenarios as $scenario)
                        <option value="{{ $scenario }}" @selected(old('document_scenario') === $scenario)>{{ $scenario }}</option>
                    @endforeach
                </select>
                <p class="mt-2 text-xs text-neutral-500">Menentukan isi Surat Jalan yang dikarang Modul 1.</p>
            </div>

            <div>
                <label for="vision_scenario" class="block text-sm font-medium text-neutral-800">
                    Skenario foto barang
                </label>
                <select name="vision_scenario"
                        id="vision_scenario"
                        class="mt-2 block w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm">
                    <option value="">Otomatis — dari hash isi berkas</option>
                    @foreach ($visionScenarios as $scenario)
                        <option value="{{ $scenario }}" @selected(old('vision_scenario') === $scenario)>{{ $scenario }}</option>
                    @endforeach
                </select>
                <p class="mt-2 text-xs text-neutral-500">Menentukan hitungan dan peringatan dari Modul 2.</p>
            </div>
        </div>

        <div class="rounded-lg border border-neutral-200 bg-neutral-50 px-4 py-3 text-xs text-neutral-600">
            <p class="font-medium text-neutral-700">Pasangan yang menarik dicoba</p>
            <ul class="mt-2 space-y-1">
                <li>
                    <span class="font-mono">mixed_units</span> +
                    <span class="font-mono">partial_occlusion</span> —
                    ada baris yang tidak bisa diverifikasi <em>dan</em> hitungan yang mungkin kurang
                </li>
                <li>
                    <span class="font-mono">clean_surat_jalan</span> +
                    <span class="font-mono">clean_stack</span> — jalur normal
                </li>
                <li>
                    <span class="font-mono">mixed_units</span> +
                    <span class="font-mono">empty</span> — foto tanpa objek sama sekali
                </li>
            </ul>
        </div>

        <div class="flex items-center gap-3 border-t border-neutral-100 pt-5">
            <button type="submit"
                    id="submit-button"
                    class="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white
                           hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-60">
                Jalankan skenario
            </button>
            <span id="pending-note" class="hidden text-sm text-neutral-600">
                Menjalankan&hellip;
            </span>
        </div>
    </form>

    <div class="mt-8">
        <a href="{{ route('inspections.create') }}" class="text-sm text-neutral-600 underline hover:text-neutral-900">
            &larr; Kembali ke pemeriksaan kiriman
        </a>
    </div>

    <script>
        // Dengan engine asli aktif, skenario diabaikan dan permintaan bisa
        // memakan menit — tombolnya tetap dikunci supaya tidak di-submit ganda.
        document.getElementById('demo-form').addEventListener('submit', function () {
            document.getElementById('submit-button').disabled = true;
            document.getElementById('pending-note').classList.remove('hidden');
        });
    </script>
@endsection
