<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

/**
 * Satu kali proses inspeksi kiriman (Modul 1 + Modul 2 + Modul 3).
 *
 * Seluruh hasil respons modul disimpan dalam bentuk array/JSON asli
 * agar tidak terjadi deviasi dari kontrak antarmuka API service AI.
 */
class Inspection extends Model
{
    use HasFactory;

    public const STATUS_QUEUED = 'queued';
    public const STATUS_PROCESSING_VISION = 'processing_vision';
    public const STATUS_PROCESSING_DOCUMENT = 'processing_document';
    public const STATUS_RECONCILING = 'reconciling';
    public const STATUS_DONE = 'done';
    public const STATUS_FAILED = 'failed';

    protected $fillable = [
        'document_original_name',
        'document_stored_path',
        'photo_original_name',
        'photo_stored_path',
        'status',
        'vision_response',
        'document_response',
        'verdict_response',
        'error',
        'started_at',
        'finished_at',
    ];

    protected function casts(): array
    {
        return [
            'vision_response' => 'array',
            'document_response' => 'array',
            'verdict_response' => 'array',
            'error' => 'array',
            'started_at' => 'datetime',
            'finished_at' => 'datetime',
        ];
    }

    public function isPending(): bool
    {
        return in_array($this->status, [
            self::STATUS_QUEUED,
            self::STATUS_PROCESSING_VISION,
            self::STATUS_PROCESSING_DOCUMENT,
            self::STATUS_RECONCILING,
        ], true);
    }

    public function isDone(): bool
    {
        return $this->status === self::STATUS_DONE;
    }

    public function hasFailed(): bool
    {
        return $this->status === self::STATUS_FAILED;
    }

    public function elapsedSeconds(): int
    {
        $start = $this->started_at ?? $this->created_at;
        if ($start === null) {
            return 0;
        }

        return (int) $start->diffInSeconds($this->finished_at ?? now(), absolute: true);
    }

    public function stepLabel(): string
    {
        return match ($this->status) {
            self::STATUS_QUEUED => 'Menunggu giliran di antrean…',
            self::STATUS_PROCESSING_VISION => 'Memeriksa foto barang (YOLO)…',
            self::STATUS_PROCESSING_DOCUMENT => 'Membaca dokumen (Qwen2-VL)…',
            self::STATUS_RECONCILING => 'Mencocokkan fisik vs dokumen…',
            self::STATUS_DONE => 'Pemeriksaan selesai.',
            self::STATUS_FAILED => 'Pemeriksaan gagal.',
            default => 'Sedang diproses…',
        };
    }
}
