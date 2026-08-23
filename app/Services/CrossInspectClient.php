<?php

namespace App\Services;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Response;
use Illuminate\Support\Facades\Http;

/**
 * Klien tunggal untuk service AI.
 *
 * Dipakai halaman alur sungguhan maupun halaman demo skenario. Keduanya
 * memanggil endpoint yang sama persis — itu disengaja, supaya demo tidak pernah
 * menempuh jalur kode yang berbeda dari produksi dan diam-diam menyembunyikan
 * kegagalan yang sebenarnya ada.
 *
 * Kegagalan dikembalikan sebagai array ber-key `failure`, bukan exception:
 * service mati atau berkas ditolak adalah keadaan normal di sini, bukan luar
 * biasa. Bentuk respons suksesnya dikunci oleh kontrak di ai/app/modules/.
 */
class CrossInspectClient
{
    /**
     * Unggah satu berkas ke endpoint modul.
     *
     * Sukses mengembalikan dua hal: `data` (hasil decode, untuk ditampilkan) dan
     * `raw` (JSON mentah, untuk diteruskan ke /crosscheck).
     *
     * Keduanya perlu disimpan karena PHP tidak bisa membedakan map kosong dari
     * list kosong: `json_decode('{"class_counts":{}}', true)` menghasilkan
     * `array()`, yang saat di-encode ulang menjadi `[]` — dan Pydantic menolaknya
     * karena kontrak menuntut objek. Itu terjadi setiap kali Modul 2 tidak
     * mendeteksi apa pun. Meneruskan bytes aslinya menghindari seluruh kelas
     * masalah ini, bukan cuma satu field yang kebetulan ketahuan.
     *
     * @param  string  $step  Kata kerja untuk pesan kegagalan, mis. "membaca dokumen".
     * @return array{data?: array, raw?: string, failure?: string}
     */
    public function upload(
        string $path,
        string $contents,
        string $filename,
        ?string $scenario,
        string $step,
    ): array {
        try {
            $response = Http::timeout($this->timeout())
                ->attach('file', $contents, $filename)
                ->post($this->url($path), $scenario ? ['scenario' => $scenario] : []);
        } catch (ConnectionException $e) {
            return $this->unreachable($step, $e->getMessage());
        }

        if ($response->failed()) {
            return $this->rejected($response, $step);
        }

        return ['data' => $response->json(), 'raw' => $response->body()];
    }

    /**
     * Vonis akhir: JSON, bukan unggahan — Modul 3 tidak menyentuh model.
     *
     * Menerima JSON mentah kedua modul, bukan array hasil decode. Body-nya
     * dirangkai sebagai string supaya respons hulu sampai ke Modul 3 persis
     * seperti yang dikirim Python.
     */
    public function reconcile(string $documentJson, string $visionJson): array
    {
        $body = '{"document":' . $documentJson . ',"vision":' . $visionJson . '}';

        try {
            $response = Http::timeout($this->timeout())
                ->withBody($body, 'application/json')
                ->post($this->url('/crosscheck'));
        } catch (ConnectionException $e) {
            return $this->unreachable('mencocokkan hasil', $e->getMessage());
        }

        return $response->failed()
            ? $this->rejected($response, 'mencocokkan hasil')
            : $response->json();
    }

    public static function failed(array $result): bool
    {
        return isset($result['failure']);
    }

    private function unreachable(string $step, string $detail): array
    {
        return [
            'failure' => "Tidak bisa menghubungi service AI saat {$step}. Pastikan container `ai` hidup. "
                . 'Saat memakai engine Qwen2-VL, permintaan pertama juga menunggu model dimuat.',
            'detail' => $detail,
        ];
    }

    private function rejected(Response $response, string $step): array
    {
        return [
            'failure' => $response->json('error.message', "Service AI menolak permintaan saat {$step}."),
            'detail' => $response->json('error.detail'),
            'code' => $response->json('error.code'),
            'status' => $response->status(),
        ];
    }

    private function url(string $path): string
    {
        return rtrim((string) config('services.ai.url'), '/') . $path;
    }

    private function timeout(): int
    {
        return (int) config('services.ai.timeout');
    }
}
