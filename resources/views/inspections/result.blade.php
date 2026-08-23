@extends('layouts.app')

@section('title', 'Hasil Pemeriksaan')
@section('heading', 'Hasil pemeriksaan')
@section('subheading', isset($documentName) ? $documentName . ' · ' . $photoName : '')

@section('content')
    @if (!empty($isDemo))
        {{-- Tanpa penanda ini, keluaran fixture terlihat sama persis dengan
             pemeriksaan sungguhan — perbedaan yang sangat penting saat demo. --}}
        <div class="mb-6 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
            Hasil <strong>skenario contoh</strong>, bukan pemeriksaan kiriman nyata.
            <a href="{{ route('demo.create') }}" class="underline hover:text-sky-950">Ganti skenario</a>
            atau <a href="{{ route('inspections.create') }}" class="underline hover:text-sky-950">periksa kiriman sungguhan</a>.
        </div>
    @endif

    @isset($failure)
        <div class="rounded-xl border border-red-200 bg-red-50 p-6">
            <h2 class="text-sm font-semibold text-red-900">Pemeriksaan gagal</h2>
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
        @include('inspections.partials.result', [
            'verdict' => $verdict,
            'document' => $document,
            'vision' => $vision,
            'documentName' => $documentName ?? null,
            'photoName' => $photoName ?? null,
            'isDemo' => $isDemo ?? false,
        ])
    @endisset

    <div class="mt-8">
        <a href="{{ route('inspections.create') }}" class="text-sm text-neutral-600 underline hover:text-neutral-900">
            &larr; Periksa kiriman lain
        </a>
    </div>
@endsection
