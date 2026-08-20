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
                <a href="{{ route('documents.create') }}" class="text-sm text-neutral-500 hover:text-neutral-800">
                    CrossInspect
                </a>
                <h1 class="mt-1 text-2xl font-semibold tracking-tight">@yield('heading')</h1>
                @hasSection('subheading')
                    <p class="mt-1 text-sm text-neutral-600">@yield('subheading')</p>
                @endif
            </header>

            @yield('content')
        </div>
    </body>
</html>
