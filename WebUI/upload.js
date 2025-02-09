async function updateMeta() {
    let data = await fetchDataAutoRetry('/api/types/', {}, 'GET');
    const types = document.getElementById('imgType');
    types.innerHTML = "";
    data.forEach(type => {
        const option = document.createElement('option');
        option.value = type;
        option.innerHTML = type;
        types.appendChild(option);
    });
}

function previewImage() {
    const file = document.getElementById('fileInput').files[0];
    const reader = new FileReader();
    reader.onload = function () {
        const img = document.getElementById('viewedImage');
        img.src = reader.result;
    }
    if (file) {
        reader.readAsDataURL(file);
    }
}

function startEdit() {
    document.getElementById('imgType').disabled = false;
    document.getElementById('imgDate').disabled = false;
    document.getElementById('imgDate').removeAttribute('readonly');
    document.getElementById('imgDate').value = new Date().toISOString().split('T')[0];
    document.getElementById('submitButton').style.display = 'block';
    const secondRow = document.getElementsByClassName('row')[1];
    const lineInput = document.createElement('input');
    lineInput.type = 'text';
    lineInput.id = 'imgTitleInput';
    lineInput.value = document.getElementById('imgTitle').innerHTML;
    document.getElementsByClassName('right')[0].insertBefore(lineInput, secondRow);
}

async function submitEdit() {
    const loadingScreen = document.getElementById('loading-screen');
    loadingScreen.style.display = 'flex';

    const type = document.getElementById('imgType').value;
    const title = document.getElementById('imgTitleInput').value;
    const date = document.getElementById('imgDate').value;
    const ifOCR = document.getElementById('imgOCR').checked;
    const url = '/api/new/image/';

    const formData = new FormData();
    formData.append('type', type);
    formData.append('title', title);
    formData.append('date', date);
    formData.append('doOCR', ifOCR);
    formData.append('image', document.getElementById('fileInput').files[0]);

    const token = localStorage.getItem('wardrobe-access-token');
    if (await checkToken(token)) {
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'Authorization': 'Bearer ' + token
            }
        });
        if (!response.ok) {
            alert('上传失败!');
            console.error('Submit edit failed:', response);
            loadingScreen.style.display = 'none';
            return;
        }
    }else{
        const refreshToken = localStorage.getItem('wardrobe-refresh-token');
        if (!refreshToken) {
            console.error('Refresh token not found!');
            window.location.href = '/login.html';
            loadingScreen.style.display = 'none';
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
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'Authorization': 'Bearer ' + token
            }
        });
        if (!response.ok) {
            alert('上传失败!');
            console.error('Submit edit failed:', response);
            loadingScreen.style.display = 'none';
            return;
        }
    }
    loadingScreen.style.display = 'none';
    alert('上传成功!');
}

updateMeta();
startEdit();