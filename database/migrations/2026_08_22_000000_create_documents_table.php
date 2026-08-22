<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Satu baris = satu kali pembacaan dokumen.
 *
 * Hasil parse disimpan supaya halaman bisa ditinggal dan dibuka lagi: dengan
 * engine asli satu dokumen bisa memakan beberapa menit, jadi menahannya di
 * memori request bukan pilihan.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('documents', function (Blueprint $table) {
            $table->id();
            $table->string('original_filename');
            $table->string('stored_path');
            $table->string('scenario')->nullable();

            // queued -> processing -> done | failed
            $table->string('status')->default('queued')->index();

            // Response kontrak apa adanya. Sengaja tidak dipecah ke kolom:
            // bentuknya milik CONTRACT.md, dan menyalinnya ke skema database
            // hanya menciptakan tempat kedua yang bisa menyimpang.
            $table->json('response')->nullable();
            $table->json('error')->nullable();

            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('documents');
    }
};
