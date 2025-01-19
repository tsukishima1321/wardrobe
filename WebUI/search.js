const OriginalImage = window.Image;

async function fetchSearchData(para) {
    let data = null;
    try {
        const accessToken = localStorage.getItem('wardrobe-access-token');
        data = await fetchJsonWithToken('/api/search/', accessToken, para);
        console.log('Search results:', data);
    } catch (error) {
        console.log('Error fetching /api/search/:', error);
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
            data = await fetchJsonWithToken('/api/search/', newTokens.access, para);
            console.log('Search results after refresh:', data);
        } catch (refreshError) {
            console.error('Error refreshing token:', refreshError);
        }
    }
    return data;
}

let currentPage = 1;
let maxPages = 99; // 最大页码

const pageNumChanged = new Event('pageNumChanged');

function renderPagination() {
    const paginationContainer = document.getElementById('pageNumbers');
    paginationContainer.innerHTML = ''; // 清空现有内容

    // 计算需要显示的页码范围
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(maxPages, currentPage + 2);

    for (let i = 1; i <= maxPages; i++) {
        if (i > 0 && i <= 2 || i >= startPage && i <= endPage || i >= maxPages - 1 && i <= maxPages) {
            const pageButton = document.createElement('button');
            pageButton.textContent = i;
            if (i === currentPage) {
                pageButton.classList.add('active-button');
            }
            pageButton.onclick = function () {
                currentPage = i;
                renderPagination();
                document.dispatchEvent(pageNumChanged);
            };
            paginationContainer.appendChild(pageButton);
        } else {
            const pageButton = document.createElement('span');
            pageButton.textContent = '...';
            paginationContainer.appendChild(pageButton);
            if (i == 3) {
                i = startPage - 1;
            } else if (i == endPage + 1) {
                i = maxPages - 2;
            }
        }
    }

    // 禁用或启用前后翻页按钮
    document.getElementById('prevButton').disabled = currentPage === 1;
    document.getElementById('nextButton').disabled = currentPage === maxPages;
}

function previousPage() {
    if (currentPage > 1) {
        currentPage--;
        renderPagination();
        document.dispatchEvent(pageNumChanged);
    }
}

function nextPage() {
    if (currentPage < maxPages) {
        currentPage++;
        renderPagination();
        document.dispatchEvent(pageNumChanged);
    }
}

document.addEventListener('pageNumChanged', function () {
    search(currentPage);
});

function goToPage() {
    const pageNumber = parseInt(document.getElementById('pageNumberInput').value);
    if (pageNumber >= 1 && pageNumber <= maxPages) {
        currentPage = pageNumber;
        renderPagination();
        document.dispatchEvent(pageNumChanged);
    }
}

function debounce(func, delay, immediate) {
    let timer;
    return function () {
        if (timer) clearTimeout(timer);
        if (immediate) {
            let firstRun = !timer;
            timer = setTimeout(() => {
                timer = null;
            }, delay);
            if (firstRun) {
                func.apply(this, arguments);
            }
        } else {
            timer = setTimeout(() => {
                func.apply(this, arguments);
            }, delay);
        }
    };
}

function search() {

    const columns = document.querySelector('.columns');
    columns.innerHTML = '';

    const keyword = document.getElementById('searchInput').value;
    const page = currentPage;
    const byName = document.getElementById('searchInTitle').checked;
    const byFullText = document.getElementById('searchInContent').checked;

    let dateFrom = document.getElementById('dateFrom').value;
    let dateTo = document.getElementById('dateTo').value;

    if (!dateFrom) {
        dateFrom = '';
    }
    if (!dateTo) {
        dateTo = '';
    }

    let sortBy = document.getElementById('sortBy').value;
    switch (sortBy) {
        case '日期':
            sortBy = 'date';
            break;
        case '文件名':
            sortBy = 'href';
            break;
        case '标题':
            sortBy = 'description';
            break;
    }

    let sort;
    const radioSortAsc = document.getElementById('sortAscending');
    if (radioSortAsc.checked) {
        sort = 'asc';
    } else {
        sort = 'desc';
    }

    const typeFilter = document.getElementById('typeFilter');
    const checkedLabels = Array.from(typeFilter.querySelectorAll('input[type="checkbox"]:checked'));
    const checkedValues = checkedLabels.map(checkbox => checkbox.parentElement.textContent.trim());
    let typeFilterString = checkedValues.join('^');

    let para = {
        searchKey: keyword,
        page: page,
        dateFrom: dateFrom,
        dateTo: dateTo,
        byName: byName,
        byFullText: byFullText,
        orderBy: sortBy,
        order: sort,
        type: typeFilterString
    };

    console.log(para);

    let data = fetchSearchData(para);
    data.then(data => {
        if (data) {
            let columns = document.querySelector('.columns');
            data.hrefList.forEach(item => {
                let figure = document.createElement('figure');
                let img = document.createElement('img');
                loadImageWithToken("/image/thumbnails/" + item.src, img);
                figure.appendChild(img);
                figure.onclick = function () {
                    let detailWindow = window.open("/detail.html?src=" + item.src, "_blank");
                };
                const figcaption = document.createElement('figcaption');
                figcaption.textContent = item.title;
                figure.appendChild(figcaption);
                columns.appendChild(figure);
            });
            let pageNum = data.totalPage;
            const pageNumberInput = document.getElementById('pageNumberInput');
            pageNumberInput.value = currentPage;
            pageNumberInput.max = pageNum;
            maxPages = pageNum;
            renderPagination();
        }
    });
}

let debounceSearch = debounce(search, 200, true);

function refreshSearch(){
    currentPage = 1;
    debounceSearch();
}

async function updateMeta() {
    const accessToken = localStorage.getItem('wardrobe-access-token');
    let data;
    try {
        const accessToken = localStorage.getItem('wardrobe-access-token');
        data = await fetchJsonWithToken('/api/types/', accessToken, {});
        console.log('Search results:', data);
    } catch (error) {
        console.log('Error fetching /api/types/:', error);
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
            data = await fetchJsonWithToken('/api/types/', accessToken, {});
            console.log('Types results after refresh:', data);
        } catch (refreshError) {
            window.location.href = '/login.html';
            console.error('Error refreshing token:', refreshError);
        }
    }
    const typeFilter = document.getElementById('typeFilter');
    typeFilter.innerHTML = "<summary>类型过滤:</summary>";
    data.forEach(type => {
        const label = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = true;
        label.appendChild(checkbox);
        label.append(type);
        typeFilter.appendChild(label);
    });
}

updateMeta();
// 初始化分页
renderPagination();
