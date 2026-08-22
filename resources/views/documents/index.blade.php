@extends('layouts.app')

@section('title', 'Riwayat Pembacaan')
@section('heading', 'Riwayat pembacaan')
@section('subheading', 'Hasil yang sudah pernah dibaca, terbaru di atas.')

@section('content')
    @php
        $badges = [
            \App\Models\Document::STATUS_QUEUED => 'bg-neutral-100 text-neutral-700',
            \App\Models\Document::STATUS_PROCESSING => 'bg-sky-100 text-sky-800',
            \App\Models\Document::STATUS_DONE => 'bg-emerald-100 text-emerald-800',
            \App\Models\Document::STATUS_FAILED => 'bg-red-100 text-red-800',
        ];
        $labels = [
            \App\Models\Document::STATUS_QUEUED => 'antre',
            \App\Models\Document::STATUS_PROCESSING => 'dibaca',
            \App\Models\Document::STATUS_DONE => 'selesai',
            \App\Models\Document::STATUS_FAILED => 'gagal',
        ];
    @endphp

    @if ($documents->isEmpty())
        <div class="rounded-xl border border-neutral-200 bg-white p-10 text-center shadow-sm">
            <p class="text-sm text-neutral-600">Belum ada dokumen yang dibaca.</p>
            <a href="{{ route('documents.create') }}"
               class="mt-4 inline-block rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700">
                Baca dokumen pertama
            </a>
        </div>
    @else
        <div class="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
            <table class="w-full text-left text-sm">
                <thead class="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                    <tr>
                        <th class="px-6 py-3 font-medium">Berkas</th>
                        <th class="px-3 py-3 font-medium">Status</th>
                        <th class="px-3 py-3 text-right font-medium">Barang</th>
                        <th class="px-3 py-3 text-right font-medium">Durasi</th>
                        <th class="px-3 py-3 font-medium">Skenario</th>
                        <th class="px-6 py-3 font-medium">Waktu</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-neutral-100">
                    @foreach ($documents as $document)
                        <tr class="hover:bg-neutral-50">
                            <td class="px-6 py-3">
                                <a href="{{ route('documents.show', $document) }}"
                                   class="font-medium text-neutral-900 underline-offset-2 hover:underline">
                                    {{ $document->original_filename }}
                                </a>
                            </td>
                            <td class="px-3 py-3">
                                <span class="rounded-full px-2 py-0.5 text-xs font-medium {{ $badges[$document->status] ?? '' }}">
                                    {{ $labels[$document->status] ?? $document->status }}
                                </span>
                            </td>
                            <td class="px-3 py-3 text-right tabular-nums">{{ $document->itemCount() ?? '—' }}</td>
                            <td class="px-3 py-3 text-right tabular-nums text-neutral-500">
                                {{ $document->isPending() ? '—' : $document->elapsedSeconds().'s' }}
                            </td>
                            <td class="px-3 py-3 font-mono text-xs text-neutral-500">{{ $document->scenario ?? '—' }}</td>
                            <td class="px-6 py-3 text-neutral-500">{{ $document->created_at->diffForHumans() }}</td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>

        <div class="mt-6">{{ $documents->links() }}</div>
    @endif

    <div class="mt-8">
        <a href="{{ route('documents.create') }}" class="text-sm text-neutral-600 underline hover:text-neutral-900">
            &larr; Baca dokumen lain
        </a>
    </div>
@endsection
