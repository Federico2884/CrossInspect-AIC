@php
    $quantity = $verdict['quantity'] ?? [];
    $counted = $quantity['counted_items'] ?? [];
    $excluded = $quantity['excluded_items'] ?? [];
    $difference = $quantity['difference'] ?? 0;
    $warnings = $verdict['warnings'] ?? [];
    $meta = $verdict['meta'] ?? [];

    // UNVERIFIABLE sengaja tidak merah: ia bukan kegagalan pemeriksaan,
    // melainkan pengakuan bahwa alat ini tidak bisa menyimpulkan.
    $verdicts = [
        'MATCH' => ['Cocok', 'Jumlah fisik sesuai dokumen.', 'border-emerald-200 bg-emerald-50 text-emerald-900'],
        'PARTIAL' => ['Cocok sebagian', 'Yang bisa diperiksa sudah sesuai, tetapi ada baris yang tidak terverifikasi.', 'border-amber-200 bg-amber-50 text-amber-900'],
        'MISMATCH' => ['Ada selisih', 'Jumlah fisik berbeda dari dokumen.', 'border-red-200 bg-red-50 text-red-900'],
        'UNVERIFIABLE' => ['Tidak dapat diverifikasi', 'Sistem tidak punya dasar untuk menyimpulkan.', 'border-neutral-300 bg-neutral-100 text-neutral-800'],
    ];
    [$label, $blurb, $style] = $verdicts[$verdict['status'] ?? 'UNVERIFIABLE'] ?? $verdicts['UNVERIFIABLE'];

    $severityStyles = [
        'error' => 'border-red-200 bg-red-50 text-red-800',
        'warning' => 'border-amber-200 bg-amber-50 text-amber-900',
        'info' => 'border-sky-200 bg-sky-50 text-sky-900',
    ];

    $reasons = [
        'UNIT_IS_WEIGHT' => 'satuan berat — tidak bisa dicacah kamera',
        'UNIT_NOT_CARDBOARD' => 'bukan kemasan kardus',
        'UNIT_UNKNOWN' => 'satuan tidak dikenali',
    ];
@endphp

@php
    // Ambil dari meta yang sudah ada — tidak perlu panggilan tambahan.
    $mockEngines = array_keys(array_filter([
        'dokumen' => ($meta['document_engine'] ?? '') === 'mock',
        'foto barang' => ($meta['vision_engine'] ?? '') === 'mock',
    ]));
@endphp

<div class="space-y-6">
    @if ($mockEngines && empty($isDemo))
        {{-- Tanpa peringatan ini, pengguna mengunggah berkas sungguhan lalu
             menerima fixture yang tampak seperti vonis nyata — dan
             menyimpulkan sistemnya rusak, bukan bahwa model belum aktif. --}}
        <div class="rounded-xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-900">
            <p class="font-semibold">Angka di bawah bukan hasil pembacaan berkas Anda.</p>
            <p class="mt-2">
                Modul {{ implode(' dan ', $mockEngines) }} masih dilayani <strong>engine mock</strong>,
                yang mengabaikan isi berkas dan memilih salah satu contoh bawaan berdasarkan
                hash berkas. Karena itu hasilnya bisa sama sekali tidak menyerupai apa yang
                Anda unggah.
            </p>
            <p class="mt-2">
                Untuk pembacaan sungguhan, jalankan ulang dengan image yang memuat model:
                <code class="rounded bg-amber-100 px-1.5 py-0.5 font-mono text-xs">AI_DOCKERFILE=Dockerfile.ml AI_ENGINE=qwen2vl</code>
            </p>
        </div>
    @endif

    <section class="rounded-xl border p-6 {{ $style }}">
        <div class="flex flex-wrap items-start justify-between gap-4">
            <div>
                <div class="text-2xl font-semibold tracking-tight">{{ $label }}</div>
                <p class="mt-1 text-sm opacity-80">{{ $blurb }}</p>
            </div>
            <div class="text-right">
                <div class="text-xs uppercase tracking-wide opacity-70">Selisih</div>
                <div class="text-3xl font-semibold tabular-nums">
                    {{ $difference > 0 ? '+' : '' }}{{ $difference }}
                </div>
            </div>
        </div>

        <dl class="mt-6 grid grid-cols-2 gap-4 border-t border-black/10 pt-5 text-sm sm:grid-cols-3">
            <div>
                <dt class="text-xs uppercase tracking-wide opacity-70">Menurut dokumen</dt>
                <dd class="mt-1 text-xl font-semibold tabular-nums">{{ $quantity['document_total'] ?? 0 }}</dd>
            </div>
            <div>
                <dt class="text-xs uppercase tracking-wide opacity-70">Terhitung di foto</dt>
                <dd class="mt-1 text-xl font-semibold tabular-nums">{{ $quantity['detected_total'] ?? 0 }}</dd>
            </div>
            <div>
                <dt class="text-xs uppercase tracking-wide opacity-70">Baris diverifikasi</dt>
                <dd class="mt-1 text-xl font-semibold tabular-nums">
                    {{ count($counted) }}<span class="text-sm font-normal opacity-70">/{{ count($counted) + count($excluded) }}</span>
                </dd>
            </div>
        </dl>

        @if (!empty($counted))
            <p class="mt-4 text-xs opacity-70">
                Angka dokumen menjumlahkan <strong>satuan kemasan</strong>, bukan isi per kemasan —
                10 karton @ 12 pcs dibandingkan sebagai 10, bukan 120.
            </p>
        @endif
    </section>

    @if (!empty($warnings))
        <section class="space-y-2">
            @foreach ($warnings as $warning)
                @php $wstyle = $severityStyles[$warning['severity'] ?? 'warning'] ?? $severityStyles['warning']; @endphp
                <div class="rounded-lg border px-4 py-3 text-sm {{ $wstyle }}">
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

    {{-- Dua parameter yang belum bisa dijawab. Sengaja netral dan bergaris
         putus-putus, tidak pernah hijau: "belum diperiksa" bukan "aman". --}}
    <section class="grid gap-4 sm:grid-cols-2">
        @foreach ([
            'Identitas produk' => $verdict['identity'] ?? [],
            'Integritas fisik' => $verdict['integrity'] ?? [],
        ] as $title => $parameter)
            @php
                $pstatus = $parameter['status'] ?? 'unavailable';
                $plabels = [
                    'unavailable' => ['Belum diperiksa', 'border-dashed border-neutral-300 bg-neutral-50 text-neutral-600'],
                    'verified' => ['Sesuai', 'border-emerald-200 bg-emerald-50 text-emerald-900'],
                    'mismatch' => ['Bermasalah', 'border-red-200 bg-red-50 text-red-900'],
                ];
                [$plabel, $pstyle] = $plabels[$pstatus] ?? $plabels['unavailable'];
            @endphp
            <div class="rounded-xl border p-5 {{ $pstyle }}">
                <div class="flex items-baseline justify-between gap-3">
                    <h2 class="text-sm font-semibold">{{ $title }}</h2>
                    <span class="text-xs font-medium uppercase tracking-wide">{{ $plabel }}</span>
                </div>
                @if (!empty($parameter['reason']))
                    <p class="mt-2 text-sm opacity-80">{{ $parameter['reason'] }}</p>
                @endif
            </div>
        @endforeach
    </section>

    <section class="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
        <div class="border-b border-neutral-100 px-6 py-4">
            <h2 class="text-sm font-semibold">
                Baris yang diverifikasi <span class="font-normal text-neutral-500">({{ count($counted) }})</span>
            </h2>
        </div>

        @if (empty($counted))
            <p class="px-6 py-8 text-center text-sm text-neutral-500">
                Tidak ada baris bersatuan kardus, jadi tidak ada yang bisa dibandingkan dengan foto.
            </p>
        @else
            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm">
                    <thead class="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                        <tr>
                            <th class="px-6 py-3 font-medium">Nama barang</th>
                            <th class="px-3 py-3 text-right font-medium">Jumlah</th>
                            <th class="px-6 py-3 font-medium">Satuan</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-neutral-100">
                        @foreach ($counted as $row)
                            <tr class="hover:bg-neutral-50">
                                <td class="px-6 py-3 font-medium">{{ $row['item_name'] }}</td>
                                <td class="px-3 py-3 text-right tabular-nums">{{ $row['quantity'] }}</td>
                                <td class="px-6 py-3">
                                    {{ $row['unit_raw'] }}
                                    <span class="ml-1 text-xs text-neutral-400">{{ $row['unit_normalized'] }}</span>
                                </td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </section>

    @if (!empty($excluded))
        <section class="overflow-hidden rounded-xl border border-amber-200 bg-white shadow-sm">
            <div class="border-b border-amber-100 bg-amber-50 px-6 py-4">
                <h2 class="text-sm font-semibold text-amber-900">
                    Tidak bisa diverifikasi <span class="font-normal opacity-70">({{ count($excluded) }})</span>
                </h2>
                <p class="mt-1 text-xs text-amber-800">
                    Baris ini tidak ikut dijumlahkan. Kamera hanya menghitung kemasan kardus,
                    jadi memasukkannya akan melaporkan selisih yang tidak nyata.
                </p>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm">
                    <thead class="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                        <tr>
                            <th class="px-6 py-3 font-medium">Nama barang</th>
                            <th class="px-3 py-3 text-right font-medium">Jumlah</th>
                            <th class="px-6 py-3 font-medium">Satuan</th>
                            <th class="px-6 py-3 font-medium">Alasan</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-neutral-100">
                        @foreach ($excluded as $row)
                            <tr>
                                <td class="px-6 py-3 font-medium">{{ $row['item_name'] }}</td>
                                <td class="px-3 py-3 text-right tabular-nums text-neutral-500">{{ $row['quantity'] }}</td>
                                <td class="px-6 py-3">{{ $row['unit_raw'] }}</td>
                                <td class="px-6 py-3 text-neutral-600">
                                    {{ $reasons[$row['reason']] ?? $row['reason'] }}
                                </td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </section>
    @endif

    <section class="rounded-xl border border-neutral-200 bg-white px-6 py-4 text-xs text-neutral-500">
        <span class="font-medium text-neutral-700">Dokumen:</span>
        <span class="font-mono">{{ ($document['document_number'] ?? '') !== '' ? $document['document_number'] : '—' }}</span>
        <span class="mx-2">·</span>engine <span class="font-mono">{{ $meta['document_engine'] ?? '?' }}</span>
        <span class="mx-2">·</span>{{ number_format(($document['meta']['processing_ms'] ?? 0) / 1000, 1) }} detik
        <br class="sm:hidden">
        <span class="mx-2 hidden sm:inline">|</span>
        <span class="font-medium text-neutral-700">Foto:</span>
        engine <span class="font-mono">{{ $meta['vision_engine'] ?? '?' }}</span>
        <span class="mx-2">·</span>{{ $vision['meta']['processing_ms'] ?? 0 }} ms
        <span class="mx-2">·</span>{{ $vision['meta']['image_width'] ?? '?' }}&times;{{ $vision['meta']['image_height'] ?? '?' }}
    </section>
</div>
