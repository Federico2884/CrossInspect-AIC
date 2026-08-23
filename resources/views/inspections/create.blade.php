@extends('layouts.app')

@section('title', 'Periksa Kiriman')
@section('heading', 'Periksa kiriman masuk')
@section('subheading', 'Unggah Surat Jalan dan foto tumpukan barang, lalu cocokkan keduanya.')

@section('content')
    @if ($errors->any())
        <div class="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <ul class="list-disc space-y-1 pl-5">
                @foreach ($errors->all() as $error)
                    <li>{{ $error }}</li>
                @endforeach
            </ul>
        </div>
    @endif

    <form method="POST"
          action="{{ route('inspections.run') }}"
          enctype="multipart/form-data"
          id="inspect-form"
          class="space-y-6 rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
        @csrf

        <div class="grid gap-6 sm:grid-cols-2">
            <div>
                <label for="document" class="block text-sm font-medium text-neutral-800">Surat Jalan / Invoice</label>
                <input type="file"
                       name="document"
                       id="document"
                       required
                       accept=".pdf,.png,.jpg,.jpeg"
                       class="mt-2 block w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm
                              file:mr-3 file:rounded-md file:border-0 file:bg-neutral-100 file:px-3 file:py-1.5
                              file:text-sm file:font-medium hover:border-neutral-400">
                <p class="mt-2 text-xs text-neutral-500">PDF, PNG, atau JPEG. Maksimal 20 MB.</p>
            </div>

            <div>
                <label for="photo" class="block text-sm font-medium text-neutral-800">Foto tumpukan barang</label>
                <input type="file"
                       name="photo"
                       id="photo"
                       required
                       accept=".png,.jpg,.jpeg,.webp"
                       class="mt-2 block w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm
                              file:mr-3 file:rounded-md file:border-0 file:bg-neutral-100 file:px-3 file:py-1.5
                              file:text-sm file:font-medium hover:border-neutral-400">
                <p class="mt-2 text-xs text-neutral-500">PNG, JPEG, atau WebP. PDF tidak diterima di sini.</p>
            </div>
        </div>

        <div class="flex flex-wrap items-center justify-between gap-3 border-t border-neutral-100 pt-5">
            <div class="flex items-center gap-3">
                <button type="submit"
                        id="submit-button"
                        class="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white
                               hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-60">
                    Periksa kiriman
                </button>
                <span id="pending-note" class="hidden text-sm text-neutral-600">
                    Memeriksa&hellip; foto selesai dalam sekejap, tetapi pembacaan dokumen dengan
                    engine Qwen2-VL bisa memakan beberapa menit.
                </span>
            </div>
            <a href="{{ route('inspections.index') }}"
               class="text-sm font-medium text-neutral-600 underline hover:text-neutral-900">
                Lihat riwayat pemeriksaan &rarr;
            </a>
        </div>
    </form>

    <div class="mt-6 space-y-1 text-sm text-neutral-500">
        <p>
            Belum punya berkas untuk dicoba?
            <a href="{{ route('demo.create') }}" class="underline hover:text-neutral-800">Jalankan skenario contoh</a>
            &mdash; tanpa unggahan.
        </p>
        <p>
            Ingin melihat seluruh field hasil pembacaan dokumen?
            <a href="{{ route('documents.create') }}" class="underline hover:text-neutral-800">Halaman uji Modul 1</a>.
        </p>
    </div>

    <script>
        // Tanpa ini, halaman yang menunggu inference beberapa menit terlihat
        // seperti hang dan mudah dikira gagal lalu di-submit ulang.
        document.getElementById('inspect-form').addEventListener('submit', function () {
            document.getElementById('submit-button').disabled = true;
            document.getElementById('pending-note').classList.remove('hidden');
        });
    </script>
@endsection
