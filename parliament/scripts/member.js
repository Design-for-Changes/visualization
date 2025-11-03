const speechList = document.querySelector(".speech-list");
const loadMoreButton = document.querySelector(".load-more");
const placeholder = document.querySelector("#summary .placeholder");
const memberNameEl = document.querySelector('[data-member-name]');
const memberMetaEl = document.querySelector('[data-member-meta]');

const params = new URLSearchParams(window.location.search);
const slug = params.get('slug');

let meetingGroups = [];
let visibleCount = 0;
const PAGE_SIZE = 5;

function extractSummary(text) {
  if (!text) return "";
  const clean = text.replace(/^○[^　 ]+　?/gm, "").replace(/\s+/g, " ").trim();
  return clean.slice(0, 100) + (clean.length > 100 ? "…" : "");
}

async function loadData() {
  try {
    if (!slug) {
      if (placeholder) placeholder.textContent = "議員が指定されていません。";
      return;
    }

    const path = `data/member_speeches/${slug}.json`;
    const res = await fetch(path);
    if (res.status === 404) {
      if (placeholder) placeholder.textContent = "データが見つかりませんでした。";
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();
    render(payload);
  } catch (error) {
    console.error(error);
    if (placeholder) placeholder.textContent = `読み込みに失敗しました: ${error.message}`;
  }
}

function render(records) {
  const groupData = Array.isArray(records)
    ? records
    : records.meetings ?? [];

  if (records && !Array.isArray(records)) {
    const memberName = records.member_name ?? slug ?? "議員";
    if (memberNameEl) memberNameEl.textContent = memberName;
    document.title = `${memberName} 障害福祉関連発言サマリー`;
    const meetingCount = groupData.length;
    const speechCount = groupData.reduce((sum, meeting) => {
      const speeches = Array.isArray(meeting?.speeches) ? meeting.speeches.length : 0;
      return sum + speeches;
    }, 0);
    if (memberMetaEl) {
      memberMetaEl.textContent = `発言数: ${speechCount} / 会議: ${meetingCount}`;
    }
  } else if (memberNameEl && slug) {
    memberNameEl.textContent = slug;
  }

  if (!Array.isArray(groupData) || groupData.length === 0) {
    if (placeholder) placeholder.textContent = "該当する発言がありませんでした。";
    return;
  }
  placeholder?.remove();
  speechList.hidden = false;

  meetingGroups = Array.isArray(records)
    ? groupByMeeting(records)
    : groupData.map((meeting) => ({
        ...meeting,
        speeches: meeting.speeches ?? []
      })).sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  visibleCount = Math.min(PAGE_SIZE, meetingGroups.length);
  renderVisibleGroups();
  updateLoadMoreButton();
}

loadData();

loadMoreButton?.addEventListener("click", () => {
  visibleCount = Math.min(visibleCount + PAGE_SIZE, meetingGroups.length);
  renderVisibleGroups();
  updateLoadMoreButton();
});

function groupByMeeting(records) {
  const map = new Map();

  records.forEach((record) => {
    const key = record.issueID || `${record.date}_${record.nameOfMeeting}_${record.issue}`;
    if (!map.has(key)) {
      map.set(key, {
        date: record.date ?? "",
        meetingName: record.nameOfMeeting ?? "会議名不明",
        issue: record.issue ?? "",
        session: record.session,
        speeches: []
      });
    }
    map.get(key).speeches.push(record);
  });

  return Array.from(map.values()).sort((a, b) => (b.date || "").localeCompare(a.date || ""));
}

function renderMeetingCard(group) {
  const tags = buildMeetingTags(group)
    .map((tag) => `<span class="tag">${tag}</span>`)
    .join("");

  const meetingTitle = group.meetingName ?? group.nameOfMeeting ?? "会議名不明";

  const speechItems = group.speeches
    .sort((a, b) => (a.speechOrder ?? 0) - (b.speechOrder ?? 0))
    .map((speech) => renderSpeechItem(speech))
    .join("");

  return `
    <article class="speech-card">
      <header class="speech-card__header">
        <div class="speech-card__meta">
          <time datetime="${group.date}">${group.date || "—"}</time>
          ${group.issue ? `<span class="speech-card__issue">${group.issue}</span>` : ""}
        </div>
        ${tags ? `<div class="tag-group">${tags}</div>` : ""}
      </header>
      <div class="speech-card__body">
        <h2>${meetingTitle}</h2>
        <ul class="speech-card__items">${speechItems}</ul>
      </div>
    </article>
  `;
}

function renderVisibleGroups() {
  const slice = meetingGroups.slice(0, visibleCount);
  const items = slice.map((group) => renderMeetingCard(group)).join("");
  speechList.innerHTML = items;
}

function updateLoadMoreButton() {
  if (!loadMoreButton) return;
  const hasMore = visibleCount < meetingGroups.length;
  loadMoreButton.hidden = !hasMore;
  if (hasMore) {
    loadMoreButton.textContent = "もっと読む";
  }
}

function buildMeetingTags(group) {
  const tags = [];
  if (group.session) tags.push(`${group.session}回国会`);
  return tags;
}

function renderSpeechItem(speech) {
  const summary = extractSummary(speech.speech);
  const content = summary || "<span class='placeholder'>要旨未整備</span>";
  const orderValue = speech.speechOrder;
  const order =
    typeof orderValue === "number" || typeof orderValue === "string"
      ? String(orderValue).padStart(3, "0")
      : null;

  return `
    <li class="speech-card__item">
      ${order ? `<a class="speech-card__order-link" href="${speech.speechURL}" target="_blank" rel="noreferrer noopener" aria-label="発言番号">${order}</a>` : ""}
      <div class="speech-card__summary">${content}</div>
    </li>
  `;
}
