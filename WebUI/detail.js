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

async function loadImage(src) {
    await updateMeta();
    let img = document.getElementById('viewedImage');
    loadImageWithToken("/image/" + src, img);
    let data = await fetchJsonWithToken('/api/get/image/', access_token, { src: src }, "POST");
    let type = document.getElementById('imgType');
    type.value = data.type;
    let title = document.getElementById('imgTitle');
    title.innerHTML = data.title;
    let date = document.getElementById('imgDate');
    date.value = data.date;
    let text = document.getElementById('imgText');
    text.value = data.text;
}

const src = new URLSearchParams(window.location.search).get('src');
if (src) {
    loadImage(src);
} else {
    console.error('No image source specified!');
}

function startEdit() {
    if (document.getElementById('imgText').getAttribute('readonly') == true) {
        alert('Please submit the current changes before editing image');
        return;
    }
    document.getElementById('imgType').disabled = false;
    document.getElementById('imgDate').disabled = false;
    document.getElementById('imgDate').removeAttribute('readonly');
    document.getElementById('editButton').style.display = 'none';
    document.getElementById('submitButton').style.display = 'block';
    const secondRow = document.getElementsByClassName('row')[1];
    const lineInput = document.createElement('input');
    lineInput.type = 'text';
    lineInput.id = 'imgTitleInput';
    lineInput.value = document.getElementById('imgTitle').innerHTML;
    document.getElementsByClassName('right')[0].insertBefore(lineInput, secondRow);
}

function startEditText() {
    if (document.getElementById('imgType').disabled == false) {
        alert('Please submit the current changes before editing text');
        return;
    }
    document.getElementById('imgText').removeAttribute('readonly');
    document.getElementById('editButtonText').style.display = 'none';
    document.getElementById('submitButtonText').style.display = 'block';
}

async function submitEdit() {
    const src = new URLSearchParams(window.location.search).get('src');
    const type = document.getElementById('imgType').value;
    const title = document.getElementById('imgTitleInput').value;
    const date = document.getElementById('imgDate').value;
    const ok = await fetchDataAutoRetry('/api/set/image/', { src: src, type: type, title: title, date: date });
    if (!ok) {
        console.error('Error updating image');
        return;
    } else {
        window.location.reload();
    }
}

async function submitEditText() {
    const src = new URLSearchParams(window.location.search).get('src');
    const text = document.getElementById('imgText').value;
    const ok = await fetchDataAutoRetry('/api/set/text/', { src: src, text: text });
    if (!ok) {
        console.error('Error updating text');
        return;
    } else {
        window.location.reload();
    }
}