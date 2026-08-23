<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Satu baris = satu sesi pemeriksaan kiriman masuk (Modul 1 + Modul 2 + Modul 3).
 *
 * Alur pemeriksaan diantrekan karena inferensi dokumen (Qwen2-VL) memakan beberapa
 * menit pada CPU. Menyimpan rekaman per tahap memungkinkan browser melakukan polling
 * status secara langsung tanpa memblokir siklus request.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('inspections', function (Blueprint $table) {
            $table->id();
            $table->string('document_original_name');
            $table->string('document_stored_path');
            $table->string('photo_original_name');
            $table->string('photo_stored_path');

            // queued -> processing_vision -> processing_document -> reconciling -> done | failed
            $table->string('status')->default('queued')->index();

            // Respons mentah & parsed dari masing-masing modul
            $table->json('vision_response')->nullable();
            $table->json('document_response')->nullable();
            $table->json('verdict_response')->nullable();
            $table->json('error')->nullable();

            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('inspections');
    }
};
