<!DOCTYPE html>
<html lang="id" class="h-full">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>@yield('title', 'CrossInspect')</title>
        @fonts
        @vite(['resources/css/app.css', 'resources/js/app.js'])
    </head>
    <body class="h-full bg-neutral-50 text-neutral-900 antialiased">
        <div class="mx-auto max-w-5xl px-6 py-10">
            <header class="mb-8">
                <div class="flex flex-wrap items-center justify-between gap-4 border-b border-neutral-200 pb-4">
                    <a href="{{ route('inspections.create') }}" class="text-base font-semibold tracking-tight text-neutral-900 hover:text-neutral-700">
                        CrossInspect
                    </a>
                    <nav class="flex items-center gap-4 text-sm font-medium">
                        <a href="{{ route('inspections.create') }}"
                           class="{{ request()->routeIs('inspections.create') ? 'text-neutral-900 font-semibold' : 'text-neutral-500 hover:text-neutral-800' }}">
                            Periksa Kiriman
                        </a>
                        <a href="{{ route('inspections.index') }}"
                           class="{{ request()->routeIs('inspections.index') ? 'text-neutral-900 font-semibold' : 'text-neutral-500 hover:text-neutral-800' }}">
                            Riwayat Pemeriksaan
                        </a>
                        <span class="text-neutral-300">|</span>
                        <a href="{{ route('demo.create') }}"
                           class="{{ request()->routeIs('demo.*') ? 'text-neutral-900 font-semibold' : 'text-neutral-500 hover:text-neutral-800' }}">
                            Demo Skenario
                        </a>
                        <a href="{{ route('documents.create') }}"
                           class="{{ request()->routeIs('documents.*') ? 'text-neutral-900 font-semibold' : 'text-neutral-500 hover:text-neutral-800' }}">
                            Uji Modul 1
                        </a>
                    </nav>
                </div>

                <div class="mt-6">
                    <h1 class="text-2xl font-semibold tracking-tight">@yield('heading')</h1>
                    @hasSection('subheading')
                        <p class="mt-1 text-sm text-neutral-600">@yield('subheading')</p>
                    @endif
                </div>
            </header>

            @yield('content')
        </div>
    </body>
</html>
