```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shoonya Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <div class="min-h-screen flex items-center justify-center">
        <div class="bg-white p-8 rounded-lg shadow-lg w-full max-w-md">
            <h2 class="text-2xl font-bold mb-6 text-center">Shoonya Login</h2>
            <div id="login-error" class="text-red-500 mb-4 hidden"></div>
            <form id="login-form">
                <div class="mb-4">
                    <label class="block text-gray-700">User ID</label>
                    <input type="text" name="user_id" class="w-full p-2 border rounded" value="FA25513" required>
                </div>
                <div class="mb-4">
                    <label class="block text-gray-700">PAN or DOB</label>
                    <input type="text" name="pan_or_dob" class="w-full p-2 border rounded" value="BWGPS1309P" required>
                </div>
                <div class="mb-4">
                    <label class="block text-gray-700">Vendor Code</label>
                    <input type="text" name="vendor_code" class="w-full p-2 border rounded" value="FA25513_U" required>
                </div>
                <div class="mb-4">
                    <label class="block text-gray-700">API Secret</label>
                    <input type="text" name="api_secret" class="w-full p-2 border rounded" value="18203e199625d0330a6c9dfa9db9620a" required>
                </div>
                <div class="mb-4">
                    <label class="block text-gray-700">IMEI</label>
                    <input type="text" name="imei" class="w-full p-2 border rounded" value="abc1234" required>
                </div>
                <div class="mb-4">
                    <label class="block text-gray-700">TOTP Secret</label>
                    <input type="text" name="totp_secret" class="w-full p-2 border rounded" required>
                </div>
                <button type="submit" class="w-full bg-blue-500 text-white p-2 rounded hover:bg-blue-600">Login</button>
            </form>
        </div>
    </div>
    <script>
        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const response = await fetch('/login', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            const errorDiv = document.getElementById('login-error');
            if (result.status === 'success') {
                window.location.href = '/dashboard';
            } else {
                errorDiv.textContent = result.message;
                errorDiv.classList.remove('hidden');
            }
        });
    </script>
</body>
</html>
```