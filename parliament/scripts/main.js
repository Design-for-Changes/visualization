const searchInput = document.querySelector('#search');
const resultsContainer = document.querySelector('#results');

let members = [];
let speechStats = {};

const SOCIAL_LABELS = {
  x: 'X',
  facebook: 'Facebook',
  instagram: 'Instagram',
  youtube: 'YouTube',
  note_blog: 'note/blog'
};

const TABLE_STRUCTURE = [
  { key: 'name', label: '議員', iconClass: null },
  {
    key: 'question_count',
    label: '主意',
    iconClass: null,
    headerClass: 'col-questions',
    cellClass: 'question-count'
  },
  {
    key: 'speech_count',
    label: '発',
    iconClass: null,
    headerClass: 'col-speech',
    cellClass: 'speech-count'
  },
  { key: 'profile', label: '国会プロフィール', iconClass: 'fa-solid fa-landmark' },
  { key: 'homepage', label: '公式サイト', iconClass: 'fa-solid fa-house' },
  { key: 'x', label: 'X', iconClass: 'fa-brands fa-x-twitter' },
  { key: 'facebook', label: 'Facebook', iconClass: 'fa-brands fa-facebook-f' },
  { key: 'instagram', label: 'Instagram', iconClass: 'fa-brands fa-instagram' },
  { key: 'youtube', label: 'YouTube', iconClass: 'fa-brands fa-youtube' },
  { key: 'note_blog', label: 'note/blog', iconClass: 'fa-solid fa-pen-to-square' }
];

const DEFAULT_PARTY = '所属未確認';
const collator = new Intl.Collator('ja');

async function loadMembers() {
  try {
    const [membersRes, indexRes] = await Promise.all([
      fetch('data/diet_members_socials_enriched.json'),
      fetch('data/member_speeches_index.json').catch(() => null)
    ]);

    if (!membersRes.ok) throw new Error(`HTTP ${membersRes.status}`);

    const payload = await membersRes.json();
    members = Array.isArray(payload) ? payload : payload.members ?? [];

    if (indexRes && indexRes.ok) {
      const indexPayload = await indexRes.json();
      speechStats = indexPayload?.index ?? {};
    } else {
      speechStats = {};
    }

    renderMembers(members);
  } catch (error) {
    console.error(error);
    resultsContainer.innerHTML = `<p class="placeholder">データの読み込みに失敗しました: ${error.message}</p>`;
  }
}

function filterMembers() {
  const term = searchInput.value.trim().toLowerCase();
  const filtered = members.filter((member) => {
    if (!term) return true;

    const haystack = [
      member.member_name,
      member.kana,
      member.party,
      member.profile_url,
      member.slug
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();

    return haystack.includes(term);
  });

  renderMembers(filtered);
}

function renderMembers(list) {
  if (!list.length) {
    resultsContainer.innerHTML =
      '<p class="placeholder">条件に一致する議員が見つかりませんでした。</p>';
    return;
  }

  const grouped = groupByPartyAndChamber(list);
  const hasSearchTerm = Boolean(searchInput?.value.trim());
  const sections = grouped
    .map(([partyName, chamberMap, partyCount]) => {
      const chamberSections = sortChambers(Array.from(chamberMap.entries()))
        .map(([chamberName, members]) => {
          const sortedMembers = members.sort((a, b) =>
            collator.compare(a.kana ?? a.member_name ?? '', b.kana ?? b.member_name ?? '')
          );

          const tableRows = sortedMembers.map((member) => renderMemberRow(member)).join('');

          return `
            <section class="chamber-group">
              <h3 class="chamber-header">${chamberName}（${members.length}名）</h3>
              <div class="table-wrapper">
                <table class="member-table">
                  <thead>
                    <tr>${TABLE_STRUCTURE.map((col) => renderHeaderCell(col)).join('')}</tr>
                  </thead>
                  <tbody>${tableRows}</tbody>
                </table>
              </div>
            </section>
          `;
        })
        .join('');

      const openAttr = hasSearchTerm ? ' open' : '';

      return `
        <details class="party-group"${openAttr}>
          <summary class="party-summary">
            <span class="party-title">${partyName}</span>
            <span class="party-count">${partyCount}名</span>
            <i class="fa-solid fa-chevron-down party-toggle" aria-hidden="true"></i>
          </summary>
          <div class="party-content">${chamberSections}</div>
        </details>
      `;
    })
    .join('');

  resultsContainer.innerHTML = sections;
}

function groupByPartyAndChamber(list) {
  const partyMap = new Map();

  list.forEach((member) => {
    const partyKey = (member.party && member.party.trim()) || DEFAULT_PARTY;
    const chamberKey = member.chamber ?? '院情報なし';

    if (!partyMap.has(partyKey)) {
      partyMap.set(partyKey, { count: 0, chambers: new Map() });
    }

    const partyEntry = partyMap.get(partyKey);
    partyEntry.count += 1;

    if (!partyEntry.chambers.has(chamberKey)) {
      partyEntry.chambers.set(chamberKey, []);
    }

    partyEntry.chambers.get(chamberKey).push(member);
  });

  return Array.from(partyMap.entries())
    .sort(([a], [b]) => collator.compare(a, b))
    .map(([partyName, { count, chambers }]) => [partyName, chambers, count]);
}

function sortChambers(entries) {
  const rank = new Map([
    ['衆議院', 0],
    ['参議院', 1]
  ]);

  return entries.sort(([a], [b]) => {
    const ra = rank.has(a) ? rank.get(a) : 99;
    const rb = rank.has(b) ? rank.get(b) : 99;
    if (ra !== rb) return ra - rb;
    return collator.compare(a, b);
  });
}

function renderMemberRow(member) {
  const socials = Object.fromEntries((member.socials ?? []).map((item) => [item.platform, item.url]));

  const cells = TABLE_STRUCTURE.map((column) => {
    if (column.key === 'name') {
      const name = member.member_name ?? '氏名不明';
      if (member.slug) {
        const href = `member.html?slug=${encodeURIComponent(member.slug)}`;
        return `<td class="cell-name"><a href="${href}">${name}</a></td>`;
      }
      return `<td class="cell-name">${name}</td>`;
    }

    if (column.key === 'speech_count') {
      const stats = member.slug ? speechStats[member.slug] : undefined;
      const count = stats?.speeches ?? 0;
      return `<td class="link-cell speech-count">${count ? count : '—'}</td>`;
    }

    if (column.key === 'question_count') {
      const stats = member.slug ? speechStats[member.slug] : undefined;
      const count = stats?.written_questions ?? 0;
      return `<td class="link-cell question-count">${count ? count : '—'}</td>`;
    }

    let url;
    if (column.key === 'homepage') {
      url = member.homepage;
    } else if (column.key === 'profile') {
      url = member.profile_url;
    } else {
      url = socials[column.key];
    }

    const extraClass = column.cellClass ? ` ${column.cellClass}` : '';
    return `<td class="link-cell${extraClass}">${renderLink(url, column)}</td>`;
  });

  return `<tr>${cells.join('')}</tr>`;
}

function renderLink(url, column) {
  const { iconClass, label } = column;
  if (!url) {
    return '<span>—</span>';
  }
  return `
    <a href="${url}" target="_blank" rel="noreferrer noopener" class="icon-link">
      ${iconClass ? `<i class="${iconClass} icon" aria-hidden="true"></i>` : ''}
      <span class="sr-only">${label}を開く</span>
    </a>
  `;
}

function renderHeaderCell(column) {
  const classAttr = column.headerClass ? ` class="${column.headerClass}"` : '';
  if (!column.iconClass) {
    return `<th${classAttr}>${column.label}</th>`;
  }
  return `
    <th${classAttr}>
      <i class="${column.iconClass} icon" aria-hidden="true"></i>
      <span class="sr-only">${column.label}</span>
    </th>
  `;
}

searchInput?.addEventListener('input', filterMembers);

loadMembers();
