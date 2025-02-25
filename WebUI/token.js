async function loadImageWithToken(url, img) {
    const token = localStorage.getItem('wardrobe-access-token') || 'default-token';
    try {
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
                // 或者使用其他 token 格式
                // 'X-Token': token
            }
        });

        if (!response.ok) {
            if (response.status === 401) {
                // Token 过期，刷新 Token
                const refreshToken = localStorage.getItem('wardrobe-refresh-token');
                if (!refreshToken) {
                    console.error('Refresh token not found!');
                    window.location.href = '/login.html';
                    return;
                }

                try {
                    const newToken = await refreshAccessToken(refreshToken);
                    localStorage.setItem('wardrobe-access-token', newToken.access);
                } catch (error) {
                    console.error('Refresh token failed:', error);
                    window.location.href = '/login.html';
                    return;
                }
                // 重新加载图片
                loadImageWithToken(url, img);
                return;
            }
            throw new Error(`Image load failed! status: ${response.status}`);
        } else {
            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);
            img.src = objectUrl;
        }
    } catch (error) {
        console.error('图片加载失败:', error);
        // 可以设置一个默认图片
        // img.src = '/default-image.jpg';
    }
}

async function fetchJsonWithToken(url, token, para, method) {
    let response;
    if (method == 'POST') {
        response = await fetch(url, {
            method: "POST",
            body: JSON.stringify(para),
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            }
        });
    } else {
        response = await fetch(url, {
            method: "GET",
            headers: {
                'Content-Type': 'form-data',
                'Authorization': 'Bearer ' + token
            }
        });
    }

    if (!response.ok) {
        if (response.status === 401) {
            return { message: 'not authorized' };
        }
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
}

async function refreshAccessToken(refreshToken) {
    const response = await fetch('/api/refresh/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ refresh: refreshToken })
    });

    if (!response.ok) {
        throw new Error(`Refresh token failed! status: ${response.status}`);
    }

    return response.json();
}

async function fetchDataAutoRetry(url, para, method = 'POST') {
    let data;
    try {
        let accessToken = localStorage.getItem('wardrobe-access-token');
        data = await fetchJsonWithToken(url, accessToken, para, method);
        if (data.message === 'not authorized') {
            const refreshToken = localStorage.getItem('wardrobe-refresh-token');
            if (!refreshToken) {
                console.log('No refresh token found. Please log in again.');
                window.location.href = '/login.html';
                return;
            }

            try {
                const newTokens = await refreshAccessToken(refreshToken);
                localStorage.setItem('wardrobe-access-token', newTokens.access);
                accessToken = localStorage.getItem('wardrobe-access-token');
                data = await fetchJsonWithToken(url, accessToken, para, method);
            } catch (refreshError) {
                window.location.href = '/login.html';
                console.error('Error refreshing token:', refreshError);
                return;
            }
        }
    } catch (error) {
        console.error('Error fetching data:', error);
        return null;
    }
    return data;
}


let access_token = localStorage.getItem('wardrobe-access-token');
if (!access_token) {
    window.location.href = '/login.html';
}

async function checkToken(token) {
    const response = await fetch('/auth/', {
        headers: {
            'Authorization': 'Bearer ' + token
        }
    });
    return response.ok;
}
