(() => {
  'use strict';

  const stage = document.querySelector('.broadcast-stage');
  const deck = document.querySelector('[data-card-deck]');
  const status = document.querySelector('[data-broadcast-status]');
  const position = document.querySelector('[data-broadcast-position]');
  const interval = Number(document.body.dataset.interval) * 1000;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let index = 0;
  let pendingDeck = null;
  let refreshing = false;
  let changing = false;

  function cards() {
    return [...deck.querySelectorAll('.broadcast-card')];
  }

  function showCard() {
    const entries = cards();
    index = entries.length ? index % entries.length : 0;
    entries.forEach((card, number) => { card.hidden = number !== index; });
    position.textContent = entries.length ? `${index + 1} / ${entries.length}` : '';
  }

  function formatTimes(root) {
    root.querySelectorAll('time').forEach((time) => {
      const value = new Date(time.dateTime);
      if (Number.isNaN(value.getTime())) return;
      time.textContent = new Intl.DateTimeFormat(undefined, {
        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
        second: '2-digit', timeZoneName: 'short',
      }).format(value);
    });
  }

  function advance() {
    if (changing || (!pendingDeck && cards().length < 2)) return;
    changing = true;
    stage.classList.add('is-fading');
    setTimeout(() => {
      const currentId = cards()[index]?.dataset.cardId;
      if (pendingDeck) {
        deck.replaceChildren(...pendingDeck.childNodes);
        pendingDeck = null;
        const previous = cards().findIndex((card) => card.dataset.cardId === currentId);
        index = previous < 0 ? 0 : previous + 1;
      } else {
        index += 1;
      }
      showCard();
      stage.classList.remove('is-fading');
      setTimeout(() => { changing = false; }, reducedMotion ? 0 : 300);
    }, reducedMotion ? 0 : 300);
  }

  async function refresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      const response = await fetch(location.href, {
        cache: 'no-cache', signal: AbortSignal.timeout(25000),
      });
      if (!response.ok) throw new Error('Scores unavailable');
      const html = new DOMParser().parseFromString(await response.text(), 'text/html');
      const next = html.querySelector('[data-card-deck]');
      if (!next) throw new Error('Missing cards');
      formatTimes(next);
      // Apply updates between cards so live score entry cannot interrupt a fade.
      pendingDeck = next;
      status.textContent = html.querySelector('[data-snapshot-stale]')?.dataset.snapshotStale === 'true'
        ? 'Cached scores' : 'Checks every 15s';
    } catch {
      // Keep the previous cards on screen through an outage or rate-limit cooldown.
      status.textContent = 'Cached scores · retrying';
    } finally {
      refreshing = false;
      setTimeout(refresh, 15000);
    }
  }

  formatTimes(deck);
  showCard();
  setInterval(advance, interval);
  setTimeout(refresh, 15000);
})();
