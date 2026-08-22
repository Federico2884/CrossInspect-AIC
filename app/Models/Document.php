<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

/**
 * Satu kali pembacaan dokumen oleh Modul 1.
 *
 * ``response`` menyimpan balasan kontrak apa adanya — lihat
 * ``ai/app/modules/document/CONTRACT.md``. View membacanya langsung sebagai
 * array; tidak ada pemetaan ke objek PHP supaya bentuknya tidak menyimpang
 * dari kontrak di dua tempat.
 */
class Document extends Model
{
    use HasFactory;

    public const STATUS_QUEUED = 'queued';
    public const STATUS_PROCESSING = 'processing';
    public const STATUS_DONE = 'done';
    public const STATUS_FAILED = 'failed';

    protected $fillable = [
        'original_filename',
        'stored_path',
        'scenario',
        'status',
        'response',
        'error',
        'started_at',
        'finished_at',
    ];

    protected function casts(): array
    {
        return [
            'response' => 'array',
            'error' => 'array',
            'started_at' => 'datetime',
            'finished_at' => 'datetime',
        ];
    }

    public function isPending(): bool
    {
        return in_array($this->status, [self::STATUS_QUEUED, self::STATUS_PROCESSING], true);
    }

    public function isDone(): bool
    {
        return $this->status === self::STATUS_DONE;
    }

    public function hasFailed(): bool
    {
        return $this->status === self::STATUS_FAILED;
    }

    /**
     * Lama pembacaan dalam detik, atau lama menunggu bila masih berjalan.
     */
    public function elapsedSeconds(): int
    {
        $start = $this->started_at ?? $this->created_at;
        if ($start === null) {
            return 0;
        }

        return (int) $start->diffInSeconds($this->finished_at ?? now(), absolute: true);
    }

    /**
     * Jumlah baris barang yang terbaca; null bila belum selesai.
     */
    public function itemCount(): ?int
    {
        return $this->isDone() ? count($this->response['items'] ?? []) : null;
    }
}
