<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('products', function (Blueprint $table) {
            $table->id();
            $table->string('name');
            $table->string('code')->unique();
            $table->text('description')->nullable();
            $table->timestamps();
        });

        Schema::create('licenses', function (Blueprint $table) {
            $table->id();
            $table->foreignId('product_id')->constrained('products')->onDelete('cascade');
            $table->string('license_key', 64)->unique()->index();
            $table->string('customer_name')->nullable();
            $table->string('customer_contact')->nullable();
            $table->string('plan_type')->default('Pro');
            $table->integer('max_slots')->default(10);
            $table->string('hwid')->nullable()->index();
            $table->string('machine_name')->nullable();
            $table->timestamp('activated_at')->nullable();
            $table->timestamp('expires_at')->nullable()->index();
            $table->string('status')->default('active')->index(); // active, suspended, revoked, expired
            $table->text('notes')->nullable();
            $table->timestamps();
        });

        Schema::create('license_logs', function (Blueprint $table) {
            $table->id();
            $table->foreignId('license_id')->nullable()->constrained('licenses')->onDelete('cascade');
            $table->string('action'); // activate, verify, heartbeat, reset_hwid, revoke
            $table->string('hwid')->nullable();
            $table->string('ip_address')->nullable();
            $table->string('client_version')->nullable();
            $table->string('status')->default('success'); // success, failed
            $table->text('message')->nullable();
            $table->timestamp('created_at')->useCurrent();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('license_logs');
        Schema::dropIfExists('licenses');
        Schema::dropIfExists('products');
    }
};
