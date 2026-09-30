<?php

use App\Http\Controllers\Api\LicenseApiController;
use Illuminate\Support\Facades\Route;

Route::prefix('v1/license')->group(function () {
    Route::post('/activate', [LicenseApiController::class, 'activate']);
    Route::post('/verify', [LicenseApiController::class, 'verify']);
    Route::match(['get', 'post'], '/check', [LicenseApiController::class, 'checkStatus']);
});
