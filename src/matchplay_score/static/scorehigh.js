(() => {
  'use strict';

  document.documentElement.classList.add('has-script');

  // DOM helpers and saved preferences
  // If you're gonna be rooting around here it probably should be easier to read eh?? :3
  const one = (selector, root = document) => root.querySelector(selector);
  const all = (selector, root = document) => [...root.querySelectorAll(selector)];
  const readSetting = (key) => {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  };
  const saveSetting = (key, value) => {
    try {
      localStorage.setItem(key, value);
    } catch {}
  };

  // Score fonts, layouts, and color themes
  const themeSelect = one('[data-theme-select]');
  const styleSelect = one('[data-style-select]');
  const scoreFontSelect = one('[data-score-font-select]');
  const setScoreFont = (value) => {
    const selected =
      value === 'alarm'
        ? 'segmented'
        : ['segmented', 'matrix', 'lcd', 'highway', 'terminal', 'plain'].includes(value)
          ? value
          : 'plain';
    document.documentElement.dataset.scoreFont = selected;
    scoreFontSelect.value = selected;
    formatScoreSeparators();
  };
  setScoreFont(readSetting('scorehigh-score-font'));
  scoreFontSelect.addEventListener('change', () => {
    setScoreFont(scoreFontSelect.value);
    saveSetting('scorehigh-score-font', scoreFontSelect.value);
  });
  const setStyle = (style) => {
    const selected = ['portal', 'windows', 'matchplay'].includes(style) ? style : 'matchplay';
    document.documentElement.dataset.style = selected;
    one('[data-portal-stylesheet]').disabled = selected !== 'portal';
    all('[data-matchplay-stylesheet], [data-monitor-stylesheet]').forEach((sheet) => {
      sheet.disabled = selected !== 'matchplay';
    });
    styleSelect.value = selected;
  };
  const monitor =
    document.documentElement.dataset.monitor === 'true' ||
    new URLSearchParams(location.search).get('display') === 'monitor';
  if (monitor) document.documentElement.dataset.monitor = 'true';
  setStyle(monitor ? 'matchplay' : readSetting('scorehigh-style'));
  styleSelect.addEventListener('change', () => {
    setStyle(styleSelect.value);
    saveSetting('scorehigh-style', styleSelect.value);
  });
  const systemTheme = matchMedia('(prefers-color-scheme: dark)');
  let themePreference = readSetting('scorehigh-theme') || 'system';
  if (!['system', 'light', 'dark'].includes(themePreference)) themePreference = 'system';
  const setTheme = () => {
    const theme =
      themePreference === 'system' ? (systemTheme.matches ? 'dark' : 'light') : themePreference;
    document.documentElement.dataset.theme = theme;
    themeSelect.value = themePreference;
    one('meta[name="theme-color"]').content = theme === 'dark' ? '#182223' : '#173c42';
  };
  setTheme();
  one('[data-theme-settings]').hidden = false;
  themeSelect.addEventListener('change', () => {
    themePreference = themeSelect.value;
    setTheme();
    saveSetting('scorehigh-theme', themePreference);
  });
  systemTheme.addEventListener('change', setTheme);
  const displaySettings = one('.display-settings');
  document.addEventListener('click', (event) => {
    if (!displaySettings.contains(event.target)) displaySettings.open = false;
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && displaySettings.open) {
      displaySettings.open = false;
      one('summary', displaySettings).focus();
    }
  });

  // Open scoring rules when linked directly to the format section
  const openFormat = () => {
    if (location.hash === '#format' && one('#format')) one('#format').open = true;
  };
  addEventListener('hashchange', openFormat);
  all('a[href="#format"]').forEach((link) =>
    link.addEventListener('click', () => {
      one('#format').open = true;
    }),
  );
  openFormat();

  // Keep commas readable when a display font uses a custom separator
  function formatScoreSeparators() {
    const segmented =
      document.documentElement.dataset.scoreFont === 'segmented' ||
      document.documentElement.dataset.monitor === 'true';
    all(
      '.monitor-game-score, .score-info > strong, .podium-total, .adjusted-score, .breakdown-total > strong, .history-total, .score-formula strong, .comparison-row > strong, .player-stats > div:nth-child(2) > strong, .score-font-preview > strong',
    ).forEach((score) => {
      if (!segmented) {
        if (score.querySelector('.score-comma')) score.textContent = score.textContent;
        return;
      }
      if (score.querySelector('.score-comma') || !score.textContent.includes(',')) return;
      const parts = score.textContent.split(',');
      score.setAttribute('aria-label', score.textContent);
      score.replaceChildren();
      parts.forEach((part, index) => {
        if (index) {
          const comma = document.createElement('span');
          comma.className = 'score-comma';
          const text = document.createElement('span');
          text.className = 'score-comma-text';
          text.textContent = ',';
          comma.append(text);
          score.append(comma);
        }
        score.append(document.createTextNode(part));
      });
    });
  }
  formatScoreSeparators();

  // Standings ticker and published snapshot updates
  const ticker = one('[data-ticker]');
  if (ticker) {
    let paused = false;
    let checking = false;
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    const prepareTicker = () => {
      const track = one('[data-ticker-track]', ticker);
      const group = one('.ticker-group', track);
      all('[data-ticker-copy]', track).forEach((node) => node.remove());
      track.classList.remove('is-running');
      if (!motion.matches && group.querySelector('a')) {
        const copy = group.cloneNode(true);
        copy.setAttribute('aria-hidden', 'true');
        copy.setAttribute('inert', '');
        copy.dataset.tickerCopy = 'true';
        track.append(copy);
        track.style.setProperty('--ticker-duration', `${Math.max(30, group.scrollWidth / 35)}s`);
        track.classList.add('is-running');
      }
    };
    const pause = one('[data-ticker-pause]', ticker);
    pause.hidden = false;
    pause.addEventListener('click', () => {
      paused = !paused;
      ticker.classList.toggle('is-paused', paused);
      pause.setAttribute('aria-pressed', String(paused));
      pause.textContent = paused ? 'Resume' : 'Pause';
    });
    motion.addEventListener('change', prepareTicker);
    prepareTicker();
    setInterval(async () => {
      if (checking || document.hidden || ticker.contains(document.activeElement)) return;
      checking = true;
      try {
        const response = await fetch(location.href, {
          signal: AbortSignal.timeout(20000),
        });
        if (!response.ok) return;
        const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
        const incoming = one('[data-ticker]', doc);
        if (incoming && incoming.dataset.updatedAt !== ticker.dataset.updatedAt) {
          one('[data-ticker-track]', ticker).replaceWith(one('[data-ticker-track]', incoming));
          ticker.dataset.updatedAt = incoming.dataset.updatedAt;
          prepareTicker();
        }
      } catch {
        /* Keep the last published standings on a failed update. */
      } finally {
        checking = false;
      }
    }, 60000);
  }

  const monitorDisplay = window.ScoreHighMonitor.create({ enabled: monitor, one, all });

  // Player search, claiming, and following (aka tracking)
  const search = one('[data-player-search]');
  const clear = one('[data-clear-search]');
  let followingOnly = false;
  let tracking = {};
  try {
    const saved = JSON.parse(readSetting('scorehigh-players') || '{}');
    if (saved && typeof saved === 'object' && !Array.isArray(saved)) tracking = saved;
  } catch {}
  const playerState = (id) => {
    const state = Object.hasOwn(tracking, id) ? tracking[id] : null;
    return {
      claimed: typeof state?.claimed === 'string' ? state.claimed : '',
      followed: Array.isArray(state?.followed)
        ? state.followed.filter((name) => typeof name === 'string')
        : [],
    };
  };
  const applyTracking = () => {
    all('[data-tracked-player]').forEach((entry) => {
      const name = entry.dataset.trackedPlayer;
      const state = playerState(entry.dataset.tournament);
      const mine = state.claimed === name;
      const followed = state.followed.includes(name);
      entry.classList.toggle('is-me', mine);
      entry.classList.toggle('is-followed', followed);
      one('[data-player-controls]', entry).hidden = false;
      const badge = one('[data-tracking-badge]', entry);
      badge.textContent = mine ? 'YOU' : 'FOLLOWING';
      badge.hidden = !mine && !followed;
      const claim = one('[data-claim-player]', entry);
      claim.hidden = Boolean(state.claimed) && !mine;
      claim.title = mine ? 'Unclaim yourself' : 'Claim as yourself';
      claim.setAttribute('aria-pressed', String(mine));
      claim.setAttribute('aria-label', `${mine ? 'Unclaim' : 'Claim'} ${name} as yourself`);
      const follow = one('[data-follow-player]', entry);
      follow.title = followed ? 'Unfollow player' : 'Follow player';
      follow.setAttribute('aria-pressed', String(followed));
      follow.setAttribute('aria-label', `${followed ? 'Unfollow' : 'Follow'} ${name}`);
    });
    const first = one('[data-tracked-player]');
    const claimStatus = one('[data-claim-status]');
    if (claimStatus && first) {
      const state = playerState(first.dataset.tournament);
      claimStatus.textContent = state.claimed ? `You: ${state.claimed}` : 'No player claimed.';
    }
  };
  const filterPlayers = () => {
    if (!search) return;
    const query = search.value.trim().toLocaleLowerCase();
    const entries = all('[data-player]');
    let visible = 0;
    entries.forEach((entry) => {
      const state = playerState(entry.dataset.tournament);
      const tracked =
        state.claimed === entry.dataset.player || state.followed.includes(entry.dataset.player);
      entry.hidden =
        !entry.dataset.player.toLocaleLowerCase().includes(query) || (followingOnly && !tracked);
      if (!entry.hidden) visible++;
    });
    one('[data-search-empty]').hidden = (!query && !followingOnly) || visible > 0;
    one('[data-player-count]').textContent =
      query || followingOnly
        ? `${visible} of ${entries.length} players`
        : `${entries.length} player${entries.length === 1 ? '' : 's'}`;
    clear.hidden = !query;
  };
  applyTracking();
  all('[data-tracking-note], [data-tracking-toolbar]').forEach((node) => {
    node.hidden = false;
  });
  const followingFilter = one('[data-following-filter]');
  followingFilter?.addEventListener('click', () => {
    followingOnly = !followingOnly;
    followingFilter.setAttribute('aria-pressed', String(followingOnly));
    followingFilter.textContent = followingOnly ? 'Show everyone' : 'Following only';
    filterPlayers();
  });
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-claim-player], [data-follow-player]');
    if (!button) return;
    const entry = button.closest('[data-tracked-player]');
    const id = entry.dataset.tournament;
    const name = entry.dataset.trackedPlayer;
    const state = playerState(id);
    if (button.hasAttribute('data-claim-player')) {
      if (state.claimed && state.claimed !== name) return;
      state.claimed = state.claimed === name ? '' : name;
    } else {
      state.followed = state.followed.includes(name)
        ? state.followed.filter((player) => player !== name)
        : [...state.followed, name];
    }
    tracking[id] = state;
    saveSetting('scorehigh-players', JSON.stringify(tracking));
    applyTracking();
    filterPlayers();
  });
  // Keep breakdown buttons in sync with their card disclosures
  const syncCardToggle = (details) => {
    const button = details.closest('.ranking-entry')?.querySelector('[data-card-toggle]');
    button?.setAttribute('aria-expanded', String(details.open));
  };
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-card-toggle]');
    if (!button) return;
    const details = button.closest('.ranking-entry').querySelector('.card-details');
    details.open = !details.open;
    syncCardToggle(details);
  });
  document.addEventListener(
    'toggle',
    (event) => {
      if (event.target.matches('.ranking-entry .card-details')) syncCardToggle(event.target);
    },
    true,
  );
  if (search) {
    one('[data-search-toolbar]').hidden = false;
    search.addEventListener('input', filterPlayers);
    clear.addEventListener('click', () => {
      search.value = '';
      filterPlayers();
      search.focus();
    });
    one('[data-expand]').addEventListener('click', (event) => {
      const button = event.currentTarget;
      const expand = button.getAttribute('aria-pressed') !== 'true';
      all('.ranking-entry:not([hidden]) .card-details').forEach((details) => {
        details.open = expand;
      });
      button.setAttribute('aria-pressed', String(expand));
      button.textContent = expand ? 'Collapse cards' : 'Expand cards';
    });
  }

  // Refresh scores while preserving player selections and open cards
  const status = one('[data-refresh-status]');
  if (!status) return;
  const refreshButton = one('[data-refresh]');
  const autoButton = one('[data-auto]');
  if (document.documentElement.dataset.examples === 'true') {
    one('[data-refresh-controls]').hidden = false;
    refreshButton.hidden = true;
    autoButton.hidden = true;
    status.textContent = 'Simulated results - no live updates';
    return;
  }
  let auto = monitor || readSetting('scorehigh-auto') !== 'off';
  let busy = false;
  let lastUpdated = new Date(status.dataset.updatedAt);
  const staticSnapshot = status.dataset.staticSnapshot === 'true';
  let failed = false;
  const updateStatus = () => {
    autoButton.textContent = `Auto: ${auto ? 'on' : 'off'}`;
    autoButton.setAttribute('aria-pressed', String(auto));
    if (failed || busy) return;
    const time = lastUpdated.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    if (staticSnapshot) {
      const date = lastUpdated.toLocaleDateString([], {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
      status.textContent = `Snapshot: ${date}, ${time} · ${auto ? 'checks every 10s.' : 'checks paused.'}`;
    } else {
      status.textContent = `Snapshot: ${time} · ${auto ? 'checks every 10s.' : 'checks paused.'}`;
    }
    if (status.dataset.cached === 'true') status.textContent += ' Cached scores; retrying.';
  };
  const refresh = async (manual = false) => {
    if (busy || (!manual && (!auto || document.hidden))) return;
    // Avoid replacing a card while someone is using its links or disclosure
    const current = one('[data-score-content]');
    if (!manual && current.contains(document.activeElement)) return;
    busy = true;
    refreshButton.disabled = true;
    status.textContent = staticSnapshot ? 'Checking published scores…' : 'Fetching scores…';
    try {
      const response = await fetch(location.href, {
        headers: { 'X-Requested-With': 'ScoreHigh' },
        signal: AbortSignal.timeout(25000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const incoming = one('[data-score-content]', doc);
      const timestamp = one('[data-refresh-status]', doc);
      if (!incoming || !timestamp) throw new Error('Incomplete scoreboard');
      const expanded = new Map(
        all('[data-card-key]', current).map((entry) => [
          entry.dataset.cardKey,
          one('details', entry)?.open,
        ]),
      );
      all('[data-card-key]', incoming).forEach((entry) => {
        const details = one('details', entry);
        if (details && expanded.has(entry.dataset.cardKey))
          details.open = expanded.get(entry.dataset.cardKey);
      });
      const scrollY = window.scrollY;
      current.replaceWith(incoming);
      all('.ranking-entry .card-details').forEach(syncCardToggle);
      formatScoreSeparators();
      applyTracking();
      filterPlayers();
      monitorDisplay.layout();
      window.scrollTo({ top: scrollY, behavior: 'instant' });
      lastUpdated = new Date(timestamp.dataset.updatedAt);
      status.dataset.cached = timestamp.dataset.cached || 'false';
      failed = false;
      delete status.dataset.error;
    } catch {
      failed = true;
      status.dataset.error = 'true';
      status.textContent =
        'Update failed. Previously fetched scores are still shown. Use Refresh to try again.';
    } finally {
      busy = false;
      refreshButton.disabled = false;
      updateStatus();
    }
  };
  one('[data-refresh-controls]').hidden = false;
  refreshButton.addEventListener('click', () => refresh(true));
  autoButton.addEventListener('click', () => {
    auto = !auto;
    saveSetting('scorehigh-auto', auto ? 'on' : 'off');
    updateStatus();
  });
  setInterval(() => refresh(), 10000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && Date.now() - lastUpdated.getTime() >= 10000) refresh();
  });
  updateStatus();
})();
