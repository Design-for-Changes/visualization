const table = document.querySelector(".speech-table");
const tbody = table?.querySelector("tbody");
const placeholder = document.querySelector("#summary .placeholder");

function extractSummary(text) {
  if (!text) return "";
  const clean = text.replace(/^○[^　 ]+　?/gm, "").replace(/\s+/g, " ").trim();
  const parts = clean.split("。").filter(Boolean);
  const firstTwo = parts.slice(0, 2).join("。");
  return (firstTwo ? `${firstTwo}。` : clean).trim();
}

function buildTagGroup(record) {
  const tags = [];
  if (record.speakerGroup) tags.push(record.speakerGroup);
  if (record.nameOfMeeting) tags.push(record.nameOfMeeting);
  if (record.session) tags.push(`${record.session}回国会`);
  return tags;
}

async function loadData() {
  try {
    const res = await fetch("data/speech_hino_sample.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const records = await res.json();
    render(records);
  } catch (error) {
    console.error(error);
    if (placeholder) placeholder.textContent = `読み込みに失敗しました: ${error.message}`;
  }
}

function render(records) {
  if (!Array.isArray(records) || records.length === 0) {
    if (placeholder) placeholder.textContent = "該当する発言がありませんでした。";
    return;
  }
  placeholder?.remove();
  table.hidden = false;

  const rows = records.map((record) => {
    const summary = extractSummary(record.speech);
    const tags = buildTagGroup(record)
      .map((tag) => `<span class="tag">${tag}</span>`)
      .join("");

    return `
      <tr>
        <td>${record.date ?? "—"}</td>
        <td>
          ${record.nameOfMeeting ?? "—"}<br />
          <small>${record.issue ?? ""}</small>
        </td>
        <td>
          ${summary || "<span class='placeholder'>要旨未整備</span>"}
          ${tags ? `<div class="tag-group">${tags}</div>` : ""}
        </td>
        <td>
          <a href="${record.speechURL}" target="_blank" rel="noreferrer noopener">テキスト</a><br />
          <a href="${record.meetingURL}" target="_blank" rel="noreferrer noopener">会議録全体</a>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = rows.join("");
}

loadData();
