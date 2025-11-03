const searchInput = document.querySelector('#search');
const chamberSelect = document.querySelector('#chamber');
const resultsContainer = document.querySelector('#results');

let members = [];

const SOCIAL_LABELS = {
  x: 'X',
  facebook: 'Facebook',
  instagram: 'Instagram',
  youtube: 'YouTube',
  note_blog: 'note/blog'
};

const TABLE_STRUCTURE = [
  { key: 'name', label: '議員', icon: null },
  { key: 'homepage', label: '公式サイト', icon: '🏠' },
  { key: 'profile', label: '国会プロフィール', icon: '🏛️' },
  { key: 'x', label: 'X', icon: '✕' },
  { key: 'facebook', label: 'Facebook', icon: 'f' },
  { key: 'instagram', label: 'Instagram', icon: '📷' },
  { key: 'youtube', label: 'YouTube', icon: '▶' },
  { key: 'note_blog', label: 'note/blog', icon: '✎' }
];

const DEFAULT_PARTY = '所属未確認';
const collator = new Intl.Collator('ja');

async function loadMembers() {
  try {
    const response = await fetch('data/diet_members_socials_enriched.json');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const payload = await response.json();
    members = Array.isArray(payload) ? payload : payload.members ?? [];
    renderMembers(members);
  } catch (error) {
    console.error(error);
    resultsContainer.innerHTML = `<p class="placeholder">データの読み込みに失敗しました: ${error.message}</p>`;
  }
}

function filterMembers() {
  const term = searchInput.value.trim().toLowerCase();
  const chamber = chamberSelect.value;

  const filtered = members.filter((member) => {
    if (chamber && member.chamber !== chamber) return false;
    if (!term) return true;

    const haystack = [
      member.member_name,
      member.kana,
      member.party,
      member.profile_url
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

      return `
        <section class="party-group">
          <h2 class="party-header">${partyName}（${partyCount}名）</h2>
          ${chamberSections}
        </section>
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
      return `<td class="cell-name">${member.member_name ?? '氏名不明'}</td>`;
    }

    let url;
    if (column.key === 'homepage') {
      url = member.homepage;
    } else if (column.key === 'profile') {
      url = member.profile_url;
    } else {
      url = socials[column.key];
    }

    return `<td class="link-cell">${renderLink(url, column)}</td>`;
  });

  return `<tr>${cells.join('')}</tr>`;
}

function renderLink(url, column) {
  const icon = column.icon ?? '';
  const label = column.label;
  if (!url) {
    return '<span>—</span>';
  }
  return `
    <a href="${url}" target="_blank" rel="noreferrer noopener" class="icon-link">
      <span class="icon" aria-hidden="true">${icon}</span>
      <span class="sr-only">${label}を開く</span>
    </a>
  `;
}

function renderHeaderCell(column) {
  if (!column.icon) {
    return `<th>${column.label}</th>`;
  }
  return `
    <th>
      <span class="icon" aria-hidden="true">${column.icon}</span>
      <span class="sr-only">${column.label}</span>
    </th>
  `;
}

searchInput?.addEventListener('input', filterMembers);
chamberSelect?.addEventListener('change', filterMembers);

loadMembers();
