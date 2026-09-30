<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Validation\ValidationException;

class AuthController extends Controller
{
    /**
     * Hiển thị trang đăng nhập quản trị viên.
     */
    public function showLogin()
    {
        if (Auth::check()) {
            return redirect()->route('admin.licenses.index');
        }
        return view('auth.login');
    }

    /**
     * Xử lý đăng nhập.
     */
    public function login(Request $request)
    {
        $credentials = $request->validate([
            'email' => 'required|string',
            'password' => 'required|string',
        ], [
            'email.required' => 'Vui lòng nhập email hoặc tài khoản quản trị.',
            'password.required' => 'Vui lòng nhập mật khẩu.',
        ]);

        $remember = $request->boolean('remember');

        // Hỗ trợ đăng nhập bằng email hoặc username
        $fieldType = filter_var($credentials['email'], FILTER_VALIDATE_EMAIL) ? 'email' : 'name';
        $loginData = [
            $fieldType => $credentials['email'],
            'password' => $credentials['password'],
        ];

        if (Auth::attempt($loginData, $remember)) {
            $request->session()->regenerate();
            return redirect()->intended(route('admin.licenses.index'))
                ->with('success', 'Đăng nhập thành công! Chào mừng trở lại, ' . Auth::user()->name);
        }

        throw ValidationException::withMessages([
            'email' => ['Tài khoản hoặc mật khẩu quản trị không chính xác.'],
        ]);
    }

    /**
     * Đăng xuất khỏi hệ thống.
     */
    public function logout(Request $request)
    {
        Auth::logout();
        $request->session()->invalidate();
        $request->session()->regenerateToken();

        return redirect()->route('login')->with('success', 'Đã đăng xuất an toàn khỏi hệ thống quản trị.');
    }
}
