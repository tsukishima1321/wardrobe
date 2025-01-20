async function updateStat(){
    let data = await fetchDataAutoRetry('/api/statistics/', {}, 'GET');
    /*{
    "overall": {
        "totalAmount": 1674,
        "lastYearAmount": 24,
        "lastMonthAmount": 24
    },
    "types": [
        {
            "type": "MEMEs",
            "totalAmount": 184,
            "lastYearAmount": 3,
            "lastMonthAmount": 3
        },
        {
            "type": "其他",
            "totalAmount": 188,
            "lastYearAmount": 5,
            "lastMonthAmount": 5
        },
        {
            "type": "美图",
            "totalAmount": 205,
            "lastYearAmount": 8,
            "lastMonthAmount": 8
        },
        {
            "type": "聊天记录",
            "totalAmount": 662,
            "lastYearAmount": 5,
            "lastMonthAmount": 5
        },
        ......
    ]
    } */
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

    types = types.sort((a, b) => b.totalAmount - a.totalAmount);

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

async function randomImage(index){
    let img = document.getElementsByClassName('viewedImage')[index];
    let data = await fetchDataAutoRetry('/api/random/', {}, 'GET');
    loadImageWithToken("/image/thumbnails/" + data.src, img);
    img.setAttribute('ori-src', data.src);
}

function showDetail(index){
    let src = document.getElementsByClassName('viewedImage')[index].getAttribute('ori-src');
    let url = new URL("detail.html", window.location.href);
    url.searchParams.set('src', src);
    window.open(url.href, "_blank");
}

function search(){
    let keyword = document.getElementById('searchText').value;
    let url = new URL("search.html", window.location.href);
    url.searchParams.set('key', keyword);
    window.open(url.href, "_blank");
}

randomButtons = document.getElementsByClassName('randomButton');
for (let i = 0; i < randomButtons.length; i++) {
    randomButtons[i].onclick = function(){
        randomImage(i);
    }
}

detailButtons = document.getElementsByClassName('detailButton');
for (let i = 0; i < detailButtons.length; i++) {
    detailButtons[i].onclick = function(){
        showDetail(i);
    }
}

updateStat();

for (let i = 0; i < document.getElementsByClassName('viewedImage').length; i++) {
    randomImage(i);
}