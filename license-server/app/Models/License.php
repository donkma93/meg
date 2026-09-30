<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Str;

class License extends Model
{
    use HasFactory;

    protected $fillable = [
        'product_id',
        'license_key',
        'customer_name',
        'customer_contact',
        'plan_type',
        'max_slots',
        'hwid',
        'machine_name',
        'activated_at',
        'expires_at',
        'status',
        'notes',
    ];

    protected $casts = [
        'activated_at' => 'datetime',
        'expires_at' => 'datetime',
        'max_slots' => 'integer',
    ];

    public function product(): BelongsTo
    {
        return $this->belongsTo(Product::class);
    }

    public function logs(): HasMany
    {
        return $this->hasMany(LicenseLog::class)->orderBy('id', 'desc');
    }

    public function isExpired(): bool
    {
        if ($this->expires_at === null) {
            return false; // Vĩnh viễn (Lifetime)
        }
        return $this->expires_at->isPast();
    }

    public function isActive(): bool
    {
        if ($this->status !== 'active') {
            return false;
        }
        return !$this->isExpired();
    }

    public static function generateLicenseKey(string $prefix = 'MEG'): string
    {
        do {
            $p1 = strtoupper(Str::random(4));
            $p2 = strtoupper(Str::random(4));
            $p3 = strtoupper(Str::random(4));
            $key = "{$prefix}-{$p1}-{$p2}-{$p3}";
        } while (static::where('license_key', $key)->exists());

        return $key;
    }
}
