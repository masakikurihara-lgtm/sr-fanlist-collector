<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>Showroom Data Fetcher</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
        }
        label {
            margin-right: 10px;
        }
        select {
            margin-right: 10px;
        }
        button {
            margin-top: 20px;
        }
        #downloadZipBtn {
            margin-top: 30px;
        }
        table {
            border-collapse: collapse;
            margin-top: 30px;
            width: 100%;
        }
        table, th, td {
            border: 1px solid #ccc;
        }
        th, td {
            padding: 8px;
            text-align: center;
        }
        th {
            background: #f2f2f2;
        }
        img.avatar {
            width: 50px;
            height: 50px;
        }
        .note {
            margin-top: 5px;
            font-size: 0.9em;
            color: #555;
            text-align: left;
        }
    </style>
</head>
<body>
    <h1>Showroom Data Fetcher</h1>
    <div>
        <label for="monthSelect">月を選択:</label>
        <select id="monthSelect">
            <option value="202501">2025年01月</option>
            <option value="202502">2025年02月</option>
            <option value="202503">2025年03月</option>
        </select>
        <button id="fetchBtn">データ取得 & ZIP作成</button>
    </div>
    <button id="downloadZipBtn" style="display:none;">ZIPをダウンロード</button>

    <div id="mergeTableContainer"></div>

    <script>
        const fetchBtn = document.getElementById("fetchBtn");
        const downloadZipBtn = document.getElementById("downloadZipBtn");
        const mergeTableContainer = document.getElementById("mergeTableContainer");

        let fetchedData = {}; // 月ごとのデータ保持
        let zipBlob = null;

        fetchBtn.addEventListener("click", async () => {
            const month = document.getElementById("monthSelect").value;
            // ダミーデータ生成
            const data = [
                { avatar_id: "1001", level: 10, title_id: 2, user_id: "u001", user_name: "ユーザーA" },
                { avatar_id: "1002", level: 15, title_id: 3, user_id: "u002", user_name: "ユーザーB" },
                { avatar_id: "1003", level: 7,  title_id: 1, user_id: "u003", user_name: "ユーザーC" }
            ];
            fetchedData[month] = data;

            await createZip();
            createMergeAndShow();
        });

        async function createZip() {
            const zip = new JSZip();

            // 各月ファイル作成
            for (const [month, data] of Object.entries(fetchedData)) {
                const header = ["avatar_id", "level", "title_id", "user_id", "user_name"];
                const csvRows = [header.join(",")];
                data.forEach(row => {
                    csvRows.push([row.avatar_id, row.level, row.title_id, row.user_id, row.user_name].join(","));
                });
                zip.file(`${month}.csv`, csvRows.join("\n"));
            }

            // マージファイル作成
            const merged = {};
            for (const data of Object.values(fetchedData)) {
                for (const row of data) {
                    if (!merged[row.user_id]) {
                        merged[row.user_id] = { ...row };
                    } else {
                        merged[row.user_id].level += row.level;
                    }
                }
            }
            // title_id 計算
            for (const row of Object.values(merged)) {
                row.title_id = Math.floor(row.level / 5);
            }
            const mergedArray = Object.values(merged).sort((a, b) => b.level - a.level);

            const header = ["avatar_id", "level", "title_id", "user_id", "user_name"];
            const csvRows = [header.join(",")];
            mergedArray.forEach(row => {
                csvRows.push([row.avatar_id, row.level, row.title_id, row.user_id, row.user_name].join(","));
            });
            zip.file(`merged.csv`, csvRows.join("\n"));

            zipBlob = await zip.generateAsync({ type: "blob" });
            downloadZipBtn.style.display = "inline-block";
        }

        function createMergeAndShow() {
            // マージ処理
            const merged = {};
            for (const data of Object.values(fetchedData)) {
                for (const row of data) {
                    if (!merged[row.user_id]) {
                        merged[row.user_id] = { ...row };
                    } else {
                        merged[row.user_id].level += row.level;
                    }
                }
            }
            for (const row of Object.values(merged)) {
                row.title_id = Math.floor(row.level / 5);
            }
            const mergedArray = Object.values(merged).sort((a, b) => b.level - a.level);

            // 順位付け
            let displayData = [];
            let lastLevel = null;
            let lastRank = 0;
            let count = 0;

            for (let i = 0; i < mergedArray.length; i++) {
                const row = mergedArray[i];
                if (row.level !== lastLevel) {
                    lastRank = i + 1;
                    lastLevel = row.level;
                }
                if (lastRank > 100) break; // 100位まで
                displayData.push({
                    rank: lastRank,
                    avatar_id: row.avatar_id,
                    level: row.level,
                    user_name: row.user_name
                });
                count++;
            }

            // テーブル作成
            let html = `
                <table>
                    <thead>
                        <tr>
                            <th>順位</th>
                            <th>アバター</th>
                            <th>レベル合計値</th>
                            <th>ユーザー名</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            displayData.forEach(row => {
                html += `
                    <tr>
                        <td>${row.rank}</td>
                        <td><img class="avatar" src="https://static.showroom-live.com/image/avatar/${row.avatar_id}.png" alt="avatar"></td>
                        <td>${row.level}</td>
                        <td>${row.user_name}</td>
                    </tr>
                `;
            });
            html += `</tbody></table>`;
            html += `<div class="note">※100位まで表示しています</div>`;
            mergeTableContainer.innerHTML = html;
        }

        downloadZipBtn.addEventListener("click", () => {
            if (zipBlob) {
                const url = URL.createObjectURL(zipBlob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "data.zip";
                a.click();
                URL.revokeObjectURL(url);
            }
        });
    </script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
</body>
</html>
