<?php

use App\Http\Controllers\DocumentParseController;
use Illuminate\Support\Facades\Route;

// '/' dan '/documents' menunjuk aksi yang sama: halaman unggah adalah satu-satunya
// muka aplikasi untuk saat ini, sementara nama rute tetap spesifik supaya modul
// lain bisa mengambil alih '/' nanti tanpa mengubah tautan yang sudah ada.
Route::get('/', [DocumentParseController::class, 'create']);
Route::get('/documents', [DocumentParseController::class, 'create'])->name('documents.create');
Route::post('/documents/parse', [DocumentParseController::class, 'parse'])->name('documents.parse');

// 'riwayat' harus dideklarasikan SEBELUM {document}, dan {document} dibatasi
// angka. Tanpa keduanya, '/documents/riwayat' ditelan oleh wildcard dan dicari
// sebagai record dengan id 'riwayat' — hasilnya 404 yang membingungkan.
Route::get('/documents/riwayat', [DocumentParseController::class, 'index'])->name('documents.index');
Route::get('/documents/{document}', [DocumentParseController::class, 'show'])
    ->whereNumber('document')
    ->name('documents.show');
Route::get('/documents/{document}/status', [DocumentParseController::class, 'status'])
    ->whereNumber('document')
    ->name('documents.status');
