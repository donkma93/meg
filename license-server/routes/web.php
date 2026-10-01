<?php

use App\Http\Controllers\Admin\AuthController;
use App\Http\Controllers\Admin\LicenseController;
use Illuminate\Support\Facades\Route;

// MEGATEAM License Server & Product Landing Routes
Route::get('/', function () {
    return view('home');
})->name('home');

// Xác thực đăng nhập / đăng xuất
Route::get('/login', [AuthController::class, 'showLogin'])->name('login');
Route::post('/login', [AuthController::class, 'login'])->name('login.post');
Route::post('/logout', [AuthController::class, 'logout'])->name('logout');

// Toàn bộ chức năng quản trị được bảo vệ bởi middleware 'auth'
Route::prefix('admin')->middleware('auth')->group(function () {
    Route::get('/licenses', [LicenseController::class, 'index'])->name('admin.licenses.index');
    Route::post('/licenses', [LicenseController::class, 'store'])->name('admin.licenses.store');
    Route::post('/licenses/{license}/reset-hwid', [LicenseController::class, 'resetHwid'])->name('admin.licenses.reset-hwid');
    Route::post('/licenses/{license}/status', [LicenseController::class, 'toggleStatus'])->name('admin.licenses.status');
    Route::post('/licenses/{license}/extend', [LicenseController::class, 'extend'])->name('admin.licenses.extend');
    Route::delete('/licenses/{license}', [LicenseController::class, 'destroy'])->name('admin.licenses.destroy');
    Route::get('/logs', [LicenseController::class, 'logs'])->name('admin.licenses.logs');
});
