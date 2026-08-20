@extends('layouts.app')

@section('title', 'Hasil Pembacaan')
@section('heading', 'Hasil pembacaan')
@section('subheading', $filename ?? '')

@section('content')
    @isset($failure)
        <div class="rounded-xl border border-red-200 bg-red-50 p-6">
            <h2 class="text-sm font-semibold text-red-900">Gagal membaca dokumen</h2>
            <p class="mt-2 text-sm text-red-800">{{ $failure }}</p>
            @if (!empty($code) || !empty($status))
                <p class="mt-3 font-mono text-xs text-red-700">
                    {{ $code ?? '' }}@if (!empty($status)) (HTTP {{ $status }})@endif
                </p>
            @endif
            @if (!empty($detail))
                <p class="mt-1 font-mono text-xs text-red-600">{{ $detail }}</p>
            @endif
        </div>
    @else
        @php
            $items = $result['items'] ?? [];
            // confidence.items sejajar dengan items — dijamin oleh kontrak.
            $itemScores = $result['confidence']['items'] ?? [];
            $warnings = $result['warnings'] ?? [];
            $meta = $result['meta'] ?? [];
            $severityStyles = [
                'error' => 'border-red-200 bg-red-50 text-red-800',
                'warning' => 'border-amber-200 bg-amber-50 text-amber-900',
                'info' => 'border-sky-200 bg-sky-50 text-sky-900',
            ];
        @endphp

        <div class="space-y-6">
            <section class="rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
                <div class="flex items-start justify-between gap-4">
                    <div>
                        <span class="rounded-full bg-neutral-100 px-2.5 py-1 text-xs font-medium text-neutral-700">
                            {{ $result['document_type'] ?? 'UNKNOWN' }}
                        </span>
                        <h2 class="mt-3 font-mono text-lg font-semibold">
                            {{ ($result['document_number'] ?? '') !== '' ? $result['document_number'] : '— tidak terbaca —' }}
                        </h2>
                    </div>
                    <div class="text-right">
                        <div class="text-xs uppercase tracking-wide text-neutral-500">Keyakinan</div>
                        <div class="text-2xl font-semibold tabular-nums">
                            {{ number_format(($result['confidence']['overall'] ?? 0) * 100, 0) }}%
                        </div>
                    </div>
                </div>

                <dl class="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 text-sm sm:grid-cols-4">
                    @foreach ([
                        'Tanggal' => $result['document_date'] ?? null,
                        'Pengirim' => $result['sender'] ?? null,
                        'Penerima' => $result['recipient'] ?? null,
                        'Halaman' => $result['page_count'] ?? null,
                    ] as $label => $value)
                        <div>
                            <dt class="text-xs uppercase tracking-wide text-neutral-500">{{ $label }}</dt>
                            <dd class="mt-1 {{ $value === null ? 'text-neutral-400' : 'text-neutral-900' }}">
                                {{ $value ?? '—' }}
                            </dd>
                        </div>
                    @endforeach
                </dl>
            </section>

            @if (!empty($warnings))
                <section class="space-y-2">
                    @foreach ($warnings as $warning)
                        @php $style = $severityStyles[$warning['severity'] ?? 'warning'] ?? $severityStyles['warning']; @endphp
                        <div class="rounded-lg border px-4 py-3 text-sm {{ $style }}">
                            <div class="flex items-baseline justify-between gap-3">
                                <span>{{ $warning['message'] }}</span>
                                <span class="shrink-0 font-mono text-xs opacity-70">{{ $warning['code'] }}</span>
                            </div>
                            @if (isset($warning['item_index']))
                                <span class="mt-1 block text-xs opacity-70">baris #{{ $warning['item_index'] + 1 }}</span>
                            @endif
                        </div>
                    @endforeach
                </section>
            @endif

            <section class="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
                <div class="border-b border-neutral-100 px-6 py-4">
                    <h2 class="text-sm font-semibold">
                        Barang <span class="font-normal text-neutral-500">({{ count($items) }})</span>
                    </h2>
                </div>

                @if (empty($items))
                    <p class="px-6 py-8 text-center text-sm text-neutral-500">Tidak ada baris barang yang terbaca.</p>
                @else
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-sm">
                            <thead class="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                                <tr>
                                    <th class="px-6 py-3 font-medium">Nama barang</th>
                                    <th class="px-3 py-3 font-medium">SKU</th>
                                    <th class="px-3 py-3 text-right font-medium">Jumlah</th>
                                    <th class="px-3 py-3 font-medium">Satuan</th>
                                    <th class="px-3 py-3 text-right font-medium">Isi/satuan</th>
                                    <th class="px-3 py-3 text-right font-medium">Total pcs</th>
                                    <th class="px-3 py-3 text-right font-medium">Hal.</th>
                                    <th class="px-6 py-3 text-right font-medium">Yakin</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-neutral-100">
                                @foreach ($items as $index => $item)
                                    @php $score = $itemScores[$index] ?? null; @endphp
                                    <tr class="hover:bg-neutral-50">
                                        <td class="px-6 py-3 font-medium">{{ $item['item_name'] }}</td>
                                        <td class="px-3 py-3 font-mono text-xs text-neutral-500">{{ $item['sku'] ?? '—' }}</td>
                                        <td class="px-3 py-3 text-right tabular-nums">{{ $item['quantity'] }}</td>
                                        <td class="px-3 py-3">
                                            {{ $item['unit_raw'] }}
                                            @if (($item['unit_normalized'] ?? null) === 'unknown')
                                                <span class="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900">tak dikenal</span>
                                            @else
                                                <span class="ml-1 text-xs text-neutral-400">{{ $item['unit_normalized'] ?? '' }}</span>
                                            @endif
                                        </td>
                                        <td class="px-3 py-3 text-right tabular-nums text-neutral-500">{{ $item['quantity_per_unit'] ?? '—' }}</td>
                                        <td class="px-3 py-3 text-right tabular-nums text-neutral-500">{{ $item['total_pieces'] ?? '—' }}</td>
                                        <td class="px-3 py-3 text-right tabular-nums text-neutral-400">{{ $item['source_page'] }}</td>
                                        <td class="px-6 py-3 text-right tabular-nums">
                                            @if ($score === null)
                                                <span class="text-neutral-400">—</span>
                                            @else
                                                {{-- 0.55 = ambang yang dipakai engine untuk LOW_CONFIDENCE_ITEM --}}
                                                <span class="{{ $score < 0.55 ? 'font-semibold text-amber-700' : 'text-neutral-600' }}">
                                                    {{ number_format($score * 100, 0) }}%
                                                </span>
                                            @endif
                                        </td>
                                    </tr>
                                @endforeach
                            </tbody>
                        </table>
                    </div>
                @endif
            </section>

            <section class="rounded-xl border border-neutral-200 bg-white px-6 py-4 text-xs text-neutral-500">
                <span class="font-medium text-neutral-700">Engine:</span>
                <span class="font-mono">{{ $meta['engine'] ?? '?' }}</span>
                <span class="mx-2">·</span>{{ $meta['device'] ?? '?' }}
                <span class="mx-2">·</span>{{ number_format(($meta['processing_ms'] ?? 0) / 1000, 1) }} detik
                @if (!empty($meta['scenario']))
                    <span class="mx-2">·</span>skenario <span class="font-mono">{{ $meta['scenario'] }}</span>
                @endif
            </section>
        </div>
    @endisset

    <div class="mt-8">
        <a href="{{ route('documents.create') }}" class="text-sm text-neutral-600 underline hover:text-neutral-900">
            &larr; Baca dokumen lain
        </a>
    </div>
@endsection
