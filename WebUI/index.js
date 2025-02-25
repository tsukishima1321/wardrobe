async function updateStat() {
    let data = await fetchDataAutoRetry('/api/statistics/', {}, 'GET');
    let overall = data.overall;
    let types = data.types;
    let totalAmount = overall.totalAmount;
    let lastYearAmount = overall.lastYearAmount;
    let lastMonthAmount = overall.lastMonthAmount;
    document.getElementById("overall-total").textContent = totalAmount;
    document.getElementById("overall-last-year").textContent = lastYearAmount;
    document.getElementById("overall-last-month").textContent = lastMonthAmount;

    let typesStatisticsDiv = document.getElementById("types-statistics");
    typesStatisticsDiv.innerHTML = ""; // Clear previous content

    types = types.sort((a, b) => b.lastMonthAmount - a.lastMonthAmount);

    types.forEach(type => {
        let typeDiv = document.createElement("div");
        typeDiv.classList.add("type-statistic");

        let typeName = document.createElement("h3");
        typeName.textContent = type.type;
        typeDiv.appendChild(typeName);

        let typeTotalAmount = document.createElement("p");
        typeTotalAmount.textContent = `总数: ${type.totalAmount}`;
        typeDiv.appendChild(typeTotalAmount);

        let typeLastYearAmount = document.createElement("p");
        typeLastYearAmount.textContent = `本年新增: ${type.lastYearAmount}`;
        typeDiv.appendChild(typeLastYearAmount);

        let typeLastMonthAmount = document.createElement("p");
        typeLastMonthAmount.textContent = `本月新增: ${type.lastMonthAmount}`;
        typeDiv.appendChild(typeLastMonthAmount);

        typesStatisticsDiv.appendChild(typeDiv);
    });
}

async function randomImage(index) {
    let img = document.getElementsByClassName('viewedImage')[index];
    let data;
    if (document.getElementsByClassName('randomType')[index].value == "全部") {
        data = await fetchDataAutoRetry('/api/random/', {}, 'GET');
    } else {
        data = await fetchDataAutoRetry('/api/random/?type=' + document.getElementsByClassName('randomType')[index].value, {}, 'GET');
    }
    loadImageWithToken("/image/thumbnails/" + data.src, img);
    img.setAttribute('ori-src', data.src);
}

function showDetail(index) {
    let src = document.getElementsByClassName('viewedImage')[index].getAttribute('ori-src');
    let url = new URL("detail.html", window.location.href);
    url.searchParams.set('src', src);
    window.open(url.href, "_blank");
}

function search() {
    let keyword = document.getElementById('searchText').value;
    let url = new URL("search.html", window.location.href);
    url.searchParams.set('key', keyword);
    window.open(url.href, "_blank");
}

randomButtons = document.getElementsByClassName('randomButton');
for (let i = 0; i < randomButtons.length; i++) {
    randomButtons[i].onclick = function () {
        randomImage(i);
    }
}

detailButtons = document.getElementsByClassName('detailButton');
for (let i = 0; i < detailButtons.length; i++) {
    detailButtons[i].onclick = function () {
        showDetail(i);
    }
}

async function updateTypes() {
    let data = await fetchDataAutoRetry('/api/types/', {}, 'GET');
    const types = document.getElementsByClassName('randomType');
    for (let i = 0; i < types.length; i++) {
        types[i].innerHTML = "";
        const option = document.createElement('option');
        option.value = "全部";
        option.innerHTML = "全部";
        types[i].appendChild(option);
        data.forEach(type => {
            const option = document.createElement('option');
            option.value = type;
            option.innerHTML = type;
            types[i].appendChild(option);
        });
    }
    types[0].value = "美图";
}

updateStat();
updateTypes().then(() => {
    for (let i = 0; i < document.getElementsByClassName('viewedImage').length; i++) {
        randomImage(i);
    }
});