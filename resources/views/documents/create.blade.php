@extends('layouts.app')

@section('title', 'Baca Dokumen')
@section('heading', 'Baca Surat Jalan')
@section('subheading', 'Unggah PDF atau foto dokumen, lalu periksa hasil pembacaannya.')

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
          action="{{ route('documents.parse') }}"
          enctype="multipart/form-data"
          id="parse-form"
          class="space-y-6 rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
        @csrf

        <div>
            <label for="file" class="block text-sm font-medium text-neutral-800">Berkas dokumen</label>
            <input type="file"
                   name="file"
                   id="file"
                   required
                   accept=".pdf,.png,.jpg,.jpeg"
                   class="mt-2 block w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm
                          file:mr-3 file:rounded-md file:border-0 file:bg-neutral-100 file:px-3 file:py-1.5
                          file:text-sm file:font-medium hover:border-neutral-400">
            <p class="mt-2 text-xs text-neutral-500">PDF, PNG, atau JPEG. Maksimal 20 MB.</p>
        </div>

        <div>
            <label for="scenario" class="block text-sm font-medium text-neutral-800">
                Skenario <span class="font-normal text-neutral-500">(khusus engine mock)</span>
            </label>
            <select name="scenario"
                    id="scenario"
                    class="mt-2 block w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm">
                <option value="">Otomatis — dipilih dari hash isi berkas</option>
                @foreach ($scenarios as $scenario)
                    <option value="{{ $scenario }}" @selected(old('scenario') === $scenario)>{{ $scenario }}</option>
                @endforeach
            </select>
            <p class="mt-2 text-xs text-neutral-500">
                Diabaikan saat engine asli (Qwen2-VL) aktif.
            </p>
        </div>

        <div class="flex items-center gap-3 border-t border-neutral-100 pt-5">
            <button type="submit"
                    id="submit-button"
                    class="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white
                           hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-60">
                Baca dokumen
            </button>
            <span id="pending-note" class="hidden text-sm text-neutral-600">
                Mengunggah&hellip;
            </span>
        </div>
    </form>

    <script>
        // Unggahan kini langsung dialihkan ke halaman tunggu, jadi ini hanya
        // mencegah submit ganda pada berkas besar.
        document.getElementById('parse-form').addEventListener('submit', function () {
            document.getElementById('submit-button').disabled = true;
            document.getElementById('pending-note').classList.remove('hidden');
        });
    </script>
@endsection
