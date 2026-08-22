<?php

use App\Http\Controllers\DocumentParseController;
use App\Http\Controllers\InspectionController;
use Illuminate\Support\Facades\Route;

// Alur cross-check adalah muka aplikasi: satu dokumen, satu foto, satu vonis.
Route::get('/', [InspectionController::class, 'create'])->name('inspections.create');
Route::post('/inspections', [InspectionController::class, 'inspect'])->name('inspections.run');

// Halaman uji Modul 1 tetap hidup di alamatnya sendiri. Ia menampilkan seluruh
// field hasil pembacaan, yang berguna saat menelusuri kenapa sebuah vonis
// meleset — sesuatu yang sengaja tidak ditampilkan halaman utama.
Route::get('/documents', [DocumentParseController::class, 'create'])->name('documents.create');
Route::post('/documents/parse', [DocumentParseController::class, 'parse'])->name('documents.parse');
