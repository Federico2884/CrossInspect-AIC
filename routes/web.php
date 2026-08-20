<?php

use App\Http\Controllers\DocumentParseController;
use Illuminate\Support\Facades\Route;

// '/' dan '/documents' menunjuk aksi yang sama: halaman unggah adalah satu-satunya
// muka aplikasi untuk saat ini, sementara nama rute tetap spesifik supaya Modul 2
// bisa mengambil alih '/' nanti tanpa mengubah tautan yang sudah ada.
Route::get('/', [DocumentParseController::class, 'create']);
Route::get('/documents', [DocumentParseController::class, 'create'])->name('documents.create');
Route::post('/documents/parse', [DocumentParseController::class, 'parse'])->name('documents.parse');
