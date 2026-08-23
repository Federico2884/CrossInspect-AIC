@extends('layouts.app')

@section('title', 'Hasil Pemeriksaan')
@section('heading', 'Hasil pemeriksaan')
@section('subheading', $inspection->document_original_name . ' · ' . $inspection->photo_original_name)

@section('content')
    @if ($inspection->isPending())
        <div class="rounded-xl border border-neutral-200 bg-white p-8 text-center shadow-sm"
             id="pending"
             data-status-url="{{ route('inspections.status', $inspection) }}">
            <div class="mx-auto h-8 w-8 animate-spin rounded-full border-3 border-neutral-200 border-t-neutral-800"></div>

            <p class="mt-5 text-sm font-medium text-neutral-800" id="pending-state">
                {{ $inspection->stepLabel() }}
            </p>

            <p class="mt-1 text-sm text-neutral-500">
                Berjalan <span id="pending-elapsed">{{ $inspection->elapsedSeconds() }}</span> detik.
            </p>

            <p class="mx-auto mt-5 max-w-md text-xs leading-relaxed text-neutral-500">
                Foto barang diproses instan dengan YOLO. Pembacaan dokumen dengan engine Qwen2-VL
                memakan waktu sekitar 2–5 menit tergantung jumlah baris barang. Halaman ini boleh
                ditinggal dan akan memuat hasil secara otomatis saat selesai.
            </p>

            <p class="mt-5 text-xs text-neutral-400">
                Butuh <code class="font-mono">php artisan queue:work</code> berjalan.
                Tanpa worker, antreannya tidak akan pernah diambil.
            </p>
        </div>

        <script>
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
                        if (data.step) {
                            state.textContent = data.step;
                        }
                        if (!data.pending) {
                            window.location.reload();
                        }
                    } catch (e) {
                        // Jaringan sesaat bermasalah bukan alasan menghentikan polling.
                    }
                }, 3000);
            })();
        </script>
    @elseif ($inspection->hasFailed())
        <div class="rounded-xl border border-red-200 bg-red-50 p-6">
            <h2 class="text-sm font-semibold text-red-900">Pemeriksaan gagal</h2>
            <p class="mt-2 text-sm text-red-800">{{ $inspection->error['failure'] ?? ($inspection->error['message'] ?? 'Penyebabnya tidak tercatat.') }}</p>
            @if (!empty($inspection->error['code']) || !empty($inspection->error['status']))
                <p class="mt-3 font-mono text-xs text-red-700">
                    {{ $inspection->error['code'] ?? '' }}@if (!empty($inspection->error['status'])) (HTTP {{ $inspection->error['status'] }})@endif
                </p>
            @endif
            @if (!empty($inspection->error['detail']))
                <p class="mt-1 font-mono text-xs text-red-600">{{ $inspection->error['detail'] }}</p>
            @endif
        </div>
    @else
        @include('inspections.partials.result', [
            'verdict' => $inspection->verdict_response,
            'document' => $inspection->document_response['data'] ?? $inspection->document_response,
            'vision' => $inspection->vision_response['data'] ?? $inspection->vision_response,
            'documentName' => $inspection->document_original_name,
            'photoName' => $inspection->photo_original_name,
            'isDemo' => false,
        ])
    @endif

    <div class="mt-8">
        <a href="{{ route('inspections.create') }}" class="text-sm text-neutral-600 underline hover:text-neutral-900">
            &larr; Periksa kiriman lain
        </a>
    </div>
@endsection
