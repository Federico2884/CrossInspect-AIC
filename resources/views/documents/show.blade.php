@extends('layouts.app')

@section('title', 'Hasil Pembacaan')
@section('heading', 'Hasil pembacaan')
@section('subheading', $document->original_filename)

@section('content')
    @if ($document->isPending())
        <div class="rounded-xl border border-neutral-200 bg-white p-8 text-center shadow-sm"
             id="pending"
             data-status-url="{{ route('documents.status', $document) }}">
            <div class="mx-auto h-8 w-8 animate-spin rounded-full border-3 border-neutral-200 border-t-neutral-800"></div>

            <p class="mt-5 text-sm font-medium text-neutral-800" id="pending-state">
                {{ $document->status === \App\Models\Document::STATUS_PROCESSING
                    ? 'Sedang dibaca service AI…'
                    : 'Menunggu giliran di antrean…' }}
            </p>

            <p class="mt-1 text-sm text-neutral-500">
                Berjalan <span id="pending-elapsed">{{ $document->elapsedSeconds() }}</span> detik.
            </p>

            {{-- Angka ini terukur, bukan tebakan: ~124 detik per halaman ditambah
                 ~17 detik per baris barang. Disebut supaya menunggu lama tidak
                 terbaca sebagai halaman yang menggantung. --}}
            <p class="mx-auto mt-5 max-w-md text-xs leading-relaxed text-neutral-500">
                Dengan engine Qwen2-VL, satu halaman memakan sekitar dua sampai lima menit
                tergantung banyaknya baris barang. Halaman ini boleh ditinggal — hasilnya
                tersimpan dan bisa dibuka lagi lewat
                <a href="{{ route('documents.index') }}" class="underline">riwayat</a>.
            </p>

            <p class="mt-5 text-xs text-neutral-400">
                Butuh <code class="font-mono">php artisan queue:work</code> berjalan.
                Tanpa worker, antreannya tidak akan pernah diambil.
            </p>
        </div>

        <script>
            // Polling sederhana, bukan websocket: satu permintaan ringan tiap
            // beberapa detik sudah cukup untuk pekerjaan yang memakan menit.
            (function () {
                const box = document.getElementById('pending');
                const state = document.getElementById('pending-state');
                const elapsed = document.getElementById('pending-elapsed');

                setInterval(async function () {
                    try {
                        const res = await fetch(box.dataset.statusUrl, {
                            headers: { 'Accept': 'application/json' },
                        });
                        if (!res.ok) return;
                        const data = await res.json();

                        elapsed.textContent = data.elapsed;
                        if (data.status === 'processing') {
                            state.textContent = 'Sedang dibaca service AI…';
                        }
                        if (!data.pending) {
                            window.location.reload();
                        }
                    } catch (e) {
                        // Jaringan sesaat bermasalah bukan alasan menghentikan
                        // polling — percobaan berikutnya beberapa detik lagi.
                    }
                }, 3000);
            })();
        </script>
    @elseif ($document->hasFailed())
        <div class="rounded-xl border border-red-200 bg-red-50 p-6">
            <h2 class="text-sm font-semibold text-red-900">Gagal membaca dokumen</h2>
            <p class="mt-2 text-sm text-red-800">{{ $document->error['message'] ?? 'Penyebabnya tidak tercatat.' }}</p>
            @if (!empty($document->error['code']))
                <p class="mt-3 font-mono text-xs text-red-700">{{ $document->error['code'] }}</p>
            @endif
            @if (!empty($document->error['detail']))
                <p class="mt-1 font-mono text-xs text-red-600">{{ $document->error['detail'] }}</p>
            @endif
        </div>
    @else
        @include('documents.partials.result', ['result' => $document->response])
    @endif

    <div class="mt-8 flex gap-4 text-sm">
        <a href="{{ route('documents.create') }}" class="text-neutral-600 underline hover:text-neutral-900">
            &larr; Baca dokumen lain
        </a>
        <a href="{{ route('documents.index') }}" class="text-neutral-600 underline hover:text-neutral-900">
            Riwayat pembacaan
        </a>
    </div>
@endsection
