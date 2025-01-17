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
                    window.location.href = '/';
                    return;
                }

                try {
                    const newToken = await refreshAccessToken(refreshToken);
                    localStorage.setItem('wardrobe-access-token', newToken.access);
                } catch (error) {
                    console.error('Refresh token failed:', error);
                    window.location.href = '/';
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

async function fetchJsonWithToken(url, token, para) {
    const response = await fetch(url, {
        method: 'POST',
        body: JSON.stringify(para),
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
        }
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
}

let access_token = localStorage.getItem('wardrobe-access-token');
if (!access_token) {
    window.location.href = '/';
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

async function updateMeta() {
    const accessToken = localStorage.getItem('wardrobe-access-token');
    let data;
    try {
        const accessToken = localStorage.getItem('wardrobe-access-token');
        data = await fetchJsonWithToken('/api/types/', accessToken, {});
    } catch (error) {
        console.log('Error fetching /api/types/:', error);
        const refreshToken = localStorage.getItem('wardrobe-refresh-token');
        if (!refreshToken) {
            console.log('No refresh token found. Please log in again.');
            window.location.href = '/';
            return;
        }

        try {
            const newTokens = await refreshAccessToken(refreshToken);
            localStorage.setItem('wardrobe-access-token', newTokens.access);

            data = await fetchJsonWithToken('/api/types/', accessToken, {});
            console.log('Types results after refresh:', data);
        } catch (refreshError) {
            console.error('Error refreshing token:', refreshError);
        }
    }
    const types = document.getElementById('imgType');
    types.innerHTML = "";
    data.forEach(type => {
        const option = document.createElement('option');
        option.value = type;
        option.innerHTML = type;
        types.appendChild(option);
    });
}

async function loadImage(src) {
    await updateMeta();
    let img = document.getElementById('viewedImage');
    loadImageWithToken("/image/" + src, img);
    let data = await fetchJsonWithToken('/api/get/image/', access_token, { src: src });
    let type = document.getElementById('imgType');
    type.value = data.type;
    let title = document.getElementById('imgTitle');
    title.innerHTML = data.title;
    let date = document.getElementById('imgDate');
    date.value = data.date;
    let text = document.getElementById('imgText');
    text.value = data.text;

    const viewer = new Viewer(img, {
        inline: true,
        zoomable: true,
        viewed() {
            viewer.zoomTo(4);
          },
    });
    viewer.show();
    
}

const src = new URLSearchParams(window.location.search).get('src');
if (src) {
    loadImage(src);
} else {
    console.error('No image source specified!');
}