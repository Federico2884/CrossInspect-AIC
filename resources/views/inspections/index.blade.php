@extends('layouts.app')

@section('title', 'Riwayat Pemeriksaan')
@section('heading', 'Riwayat pemeriksaan')
@section('subheading', 'Daftar pemeriksaan fisik vs dokumen masuk, terbaru di atas.')

@section('content')
    @php
        $verdictBadges = [
            'MATCH' => 'bg-emerald-100 text-emerald-800',
            'PARTIAL' => 'bg-amber-100 text-amber-800',
            'MISMATCH' => 'bg-red-100 text-red-800',
            'UNVERIFIABLE' => 'bg-neutral-100 text-neutral-800',
        ];
        $verdictLabels = [
            'MATCH' => 'Cocok',
            'PARTIAL' => 'Cocok sebagian',
            'MISMATCH' => 'Ada selisih',
            'UNVERIFIABLE' => 'Belum diverifikasi',
        ];
        $statusBadges = [
            \App\Models\Inspection::STATUS_QUEUED => 'bg-neutral-100 text-neutral-700',
            \App\Models\Inspection::STATUS_PROCESSING_VISION => 'bg-sky-100 text-sky-800',
            \App\Models\Inspection::STATUS_PROCESSING_DOCUMENT => 'bg-sky-100 text-sky-800',
            \App\Models\Inspection::STATUS_RECONCILING => 'bg-sky-100 text-sky-800',
            \App\Models\Inspection::STATUS_FAILED => 'bg-red-100 text-red-800',
        ];
        $statusLabels = [
            \App\Models\Inspection::STATUS_QUEUED => 'antre',
            \App\Models\Inspection::STATUS_PROCESSING_VISION => 'foto',
            \App\Models\Inspection::STATUS_PROCESSING_DOCUMENT => 'dokumen',
            \App\Models\Inspection::STATUS_RECONCILING => 'rekonsiliasi',
            \App\Models\Inspection::STATUS_FAILED => 'gagal',
        ];
    @endphp

    @if ($inspections->isEmpty())
        <div class="rounded-xl border border-neutral-200 bg-white p-10 text-center shadow-sm">
            <p class="text-sm text-neutral-600">Belum ada pemeriksaan kiriman yang dilakukan.</p>
            <a href="{{ route('inspections.create') }}"
               class="mt-4 inline-block rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700">
                Periksa kiriman pertama
            </a>
        </div>
    @else
        <div class="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
            <table class="w-full text-left text-sm">
                <thead class="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                    <tr>
                        <th class="px-6 py-3 font-medium">Surat Jalan / Dokumen</th>
                        <th class="px-3 py-3 font-medium">Foto Barang</th>
                        <th class="px-3 py-3 font-medium">Vonis</th>
                        <th class="px-3 py-3 text-right font-medium">Selisih</th>
                        <th class="px-3 py-3 text-right font-medium">Durasi</th>
                        <th class="px-6 py-3 font-medium">Waktu</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-neutral-100">
                    @foreach ($inspections as $inspection)
                        @php
                            $vStatus = $inspection->verdictStatus();
                            $diff = $inspection->quantityDifference();
                        @endphp
                        <tr class="hover:bg-neutral-50">
                            <td class="px-6 py-3">
                                <a href="{{ route('inspections.show', $inspection) }}"
                                   class="font-medium text-neutral-900 underline-offset-2 hover:underline">
                                    {{ $inspection->documentNumber() ?? $inspection->document_original_name }}
                                </a>
                                @if ($inspection->documentNumber() && $inspection->documentNumber() !== $inspection->document_original_name)
                                    <span class="block text-xs text-neutral-400 font-normal">
                                        {{ $inspection->document_original_name }}
                                    </span>
                                @endif
                            </td>
                            <td class="px-3 py-3 text-neutral-600 text-xs font-mono">
                                {{ $inspection->photo_original_name }}
                            </td>
                            <td class="px-3 py-3">
                                @if ($inspection->isDone() && $vStatus)
                                    <span class="rounded-full px-2.5 py-0.5 text-xs font-medium {{ $verdictBadges[$vStatus] ?? 'bg-neutral-100 text-neutral-800' }}">
                                        {{ $verdictLabels[$vStatus] ?? $vStatus }}
                                    </span>
                                @else
                                    <span class="rounded-full px-2 py-0.5 text-xs font-medium {{ $statusBadges[$inspection->status] ?? '' }}">
                                        {{ $statusLabels[$inspection->status] ?? $inspection->status }}
                                    </span>
                                @endif
                            </td>
                            <td class="px-3 py-3 text-right tabular-nums font-medium {{ $diff !== null && $diff !== 0 ? 'text-red-700 font-semibold' : 'text-neutral-700' }}">
                                @if ($diff !== null)
                                    {{ $diff > 0 ? '+' : '' }}{{ $diff }}
                                @else
                                    <span class="text-neutral-400 font-normal">—</span>
                                @endif
                            </td>
                            <td class="px-3 py-3 text-right tabular-nums text-neutral-500">
                                {{ $inspection->isPending() ? '—' : $inspection->elapsedSeconds().'s' }}
                            </td>
                            <td class="px-6 py-3 text-neutral-500">{{ $inspection->created_at->diffForHumans() }}</td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>

        <div class="mt-6">{{ $inspections->links() }}</div>
    @endif

    <div class="mt-8">
        <a href="{{ route('inspections.create') }}" class="text-sm text-neutral-600 underline hover:text-neutral-900">
            &larr; Periksa kiriman baru
        </a>
    </div>
@endsection
