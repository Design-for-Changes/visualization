const speechList = document.querySelector(".speech-list");
const loadMoreButton = document.querySelector(".load-more");
const placeholder = document.querySelector("#summary .placeholder");
const memberNameEl = document.querySelector('[data-member-name]');
const memberMetaEl = document.querySelector('[data-member-meta]');
const leagueSection = document.querySelector('#leagues');
const leagueList = leagueSection?.querySelector('.league-list');
const leaguePlaceholder = leagueSection?.querySelector('.placeholder');
const questionsSection = document.querySelector('#questions');
const questionsPlaceholder = questionsSection?.querySelector('.placeholder');
const questionsList = document.querySelector('.question-list');

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
    const [speechRes, rosterRes] = await Promise.all([
      fetch(path),
      fetch('data/diet_members_socials_enriched.json').catch(() => null)
    ]);

    let memberProfile = null;
    if (rosterRes && rosterRes.ok) {
      const rosterPayload = await rosterRes.json();
      const rosterList = Array.isArray(rosterPayload) ? rosterPayload : rosterPayload.members ?? [];
      memberProfile = rosterList.find((entry) => entry.slug === slug) ?? null;
    }

    if (speechRes.status === 404) {
      renderFallback(memberProfile);
      return;
    }
    if (!speechRes.ok) throw new Error(`HTTP ${speechRes.status}`);

    const payload = await speechRes.json();
    render(payload, memberProfile);
  } catch (error) {
    console.error(error);
    if (placeholder) placeholder.textContent = `読み込みに失敗しました: ${error.message}`;
  }
}

function render(records, profile) {
  const groupData = Array.isArray(records)
    ? records
    : records.meetings ?? [];

  if (records && !Array.isArray(records)) {
    const memberName = records.member_name ?? profile?.member_name ?? slug ?? "議員";
    if (memberNameEl) memberNameEl.textContent = memberName;
    document.title = `${memberName} 障害福祉関連発言サマリー`;
    const meetingCount = groupData.length;
    const speechCount = groupData.reduce((sum, meeting) => {
      const speeches = Array.isArray(meeting?.speeches) ? meeting.speeches.length : 0;
      return sum + speeches;
    }, 0);
    const writtenQuestions = Array.isArray(records.written_questions)
      ? records.written_questions
      : [];
    const questionCount = writtenQuestions.length;
    if (memberMetaEl) {
      const metaParts = [
        `主意書: ${questionCount}`,
        `発言数: ${speechCount}`,
        `会議: ${meetingCount}`
      ];
      if (typeof profile?.disability_league_count === 'number') {
        metaParts.push(`議連: ${profile.disability_league_count}`);
      }
      memberMetaEl.textContent = metaParts.join(' / ');
    }
    renderDisabilityLeagues(profile?.disability_leagues ?? []);
    renderWrittenQuestions(writtenQuestions);
  } else if (memberNameEl && slug) {
    memberNameEl.textContent = slug;
  }

  if (!Array.isArray(groupData) || groupData.length === 0) {
    if (placeholder) placeholder.textContent = "該当する発言がありませんでした。";
    meetingGroups = [];
    if (loadMoreButton) loadMoreButton.hidden = true;
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

function renderWrittenQuestions(list) {
  if (!questionsSection || !questionsList) return;

  const items = Array.isArray(list) ? [...list] : [];
  if (!items.length) {
    questionsPlaceholder && (questionsPlaceholder.textContent = '該当する質問主意書はありません。');
    questionsSection.hidden = false;
    questionsList.hidden = true;
    return;
  }

  const sorted = items.sort((a, b) => {
    const sessionDiff = (b.session ?? 0) - (a.session ?? 0);
    if (sessionDiff !== 0) return sessionDiff;
    return (b.number ?? 0) - (a.number ?? 0);
  });

  const markup = sorted
    .map((question) => renderQuestionItem(question))
    .join('');

  questionsPlaceholder?.remove();
  questionsList.hidden = false;
  questionsSection.hidden = false;
  questionsList.innerHTML = markup;
}

function renderDisabilityLeagues(leagues) {
  if (!leagueSection || !leagueList) return;
  const items = Array.isArray(leagues) ? leagues : [];
  leagueSection.hidden = false;
  if (!items.length) {
    if (leaguePlaceholder) leaguePlaceholder.textContent = '該当する議連はありません。';
    leagueList.hidden = true;
    return;
  }
  leaguePlaceholder?.remove();
  leagueList.hidden = false;
  leagueList.innerHTML = items.map((name) => `<li>${name}</li>`).join('');
}

loadData();

loadMoreButton?.addEventListener("click", () => {
  visibleCount = Math.min(visibleCount + PAGE_SIZE, meetingGroups.length);
  renderVisibleGroups();
  updateLoadMoreButton();
});

function renderFallback(profile) {
  const memberName = profile?.member_name ?? slug ?? "議員";
  if (memberNameEl) memberNameEl.textContent = memberName;
  document.title = `${memberName} 障害福祉関連サマリー`;
  if (memberMetaEl) {
    const parts = [];
    if (typeof profile?.disability_league_count === "number") {
      parts.push(`議連: ${profile.disability_league_count}`);
    }
    memberMetaEl.textContent = parts.length ? parts.join(" / ") : "国会発言データが未登録です。";
  }
  renderDisabilityLeagues(profile?.disability_leagues ?? []);
  if (questionsSection) {
    questionsSection.hidden = true;
  }
  const summarySection = document.querySelector("#summary");
  if (summarySection) {
    summarySection.innerHTML =
      '<p class="placeholder">この議員の障害福祉関連発言データはまだ登録されていません。</p>';
  }
  placeholder?.remove();
  loadMoreButton?.setAttribute("hidden", "hidden");
}

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
  if (meetingGroups.length <= PAGE_SIZE) {
    loadMoreButton.hidden = true;
    return;
  }
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

function renderQuestionItem(question) {
  const {
    title,
    session,
    number,
    status,
    question_html_url,
    question_pdf_url,
    answer_html_url,
    answer_pdf_url,
    matched_keywords = []
  } = question ?? {};

  const sessionLabel = session ? `第${session}回` : '';
  const numberLabel = typeof number === 'number' ? `第${number}号` : '';
  const metaParts = [sessionLabel, numberLabel, status].filter(Boolean);
  const keywordTags = Array.isArray(matched_keywords) && matched_keywords.length
    ? `<ul class="question-tags">${matched_keywords.map((kw) => `<li>${kw}</li>`).join('')}</ul>`
    : '';

  const linkItems = [
    question_html_url && `<a href="${question_html_url}" target="_blank" rel="noreferrer noopener">質問 (HTML)</a>`,
    question_pdf_url && `<a href="${question_pdf_url}" target="_blank" rel="noreferrer noopener">質問PDF</a>`,
    answer_html_url && `<a href="${answer_html_url}" target="_blank" rel="noreferrer noopener">答弁 (HTML)</a>`,
    answer_pdf_url && `<a href="${answer_pdf_url}" target="_blank" rel="noreferrer noopener">答弁PDF</a>`
  ].filter(Boolean);

  const links = linkItems.length
    ? `<div class="question-links">${linkItems.map((item) => `<span>${item}</span>`).join('')}</div>`
    : '';

  return `
    <li class="question-item">
      <h3>
        ${question_html_url
          ? `<a href="${question_html_url}" target="_blank" rel="noreferrer noopener">${title ?? 'タイトル不明'}</a>`
          : (title ?? 'タイトル不明')}
      </h3>
      ${metaParts.length ? `<p class="question-meta">${metaParts.join(' / ')}</p>` : ''}
      ${links}
      ${keywordTags}
    </li>
  `;
}
