// Monitor stuff here is to make it work good on the big ones and readable at-a-glance. It's not fully featured or smth
(() => {
  'use strict';
  window.ScoreHighMonitor = {
    create({ enabled, one, all }) {
      let screenPage = 0;
      let screenPages = 1;
      const screenRows = 5;
      let laterScreenRows = 8;
      let rotating = true;
      let screenFading = false;
      const layoutMonitor = () => {
        if (!enabled || !one('.scoreboard')) return;
        const entries = all('.ranking-entry');
        const pinned = Math.min(3, entries.length);
        const remainder = entries.length - pinned;
        laterScreenRows = Math.max(
          1,
          Math.min(
            8,
            Math.floor(
              (one('.scoreboard').clientHeight - one('.score-column-head').offsetHeight) / 80,
            ),
          ),
        );
        screenPages = 1 + Math.ceil(Math.max(0, remainder - screenRows) / laterScreenRows);
        screenPage = Math.min(screenPage, screenPages - 1);
        one('.monitor-podium').hidden = screenPage > 0;
        one('.scoreboard').classList.toggle('monitor-finalists', screenPage === 0);
        entries.forEach((entry, index) => {
          const position = index - pinned;
          const page =
            position < screenRows ? 0 : 1 + Math.floor((position - screenRows) / laterScreenRows);
          entry.classList.toggle('screen-page-hidden', index < pinned || page !== screenPage);
        });
        one('[data-monitor-page]').textContent =
          `Page ${screenPage + 1} / ${screenPages} · ${entries.length} players`;
        all('[data-monitor-prev], [data-monitor-next]').forEach((button) => {
          button.disabled = screenPages < 2;
        });
        one('[data-monitor-rotate]').disabled = screenPages < 2;
        // Keep row scores large; shrink only the unusually long ones to fit.
        all('.monitor-game-score').forEach((score) => {
          if (!score.getClientRects().length) return;
          score.style.fontSize = '';
          if (score.scrollWidth > score.clientWidth) {
            const size = parseFloat(getComputedStyle(score).fontSize);
            score.style.fontSize = `${Math.floor((size * score.clientWidth * 10) / score.scrollWidth) / 10}px`;
          }
        });
      };
      const changeScreenPage = (direction) => {
        if (screenPages < 2 || screenFading) return;
        const advance = () => {
          screenPage = (screenPage + direction + screenPages) % screenPages;
          layoutMonitor();
        };
        if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
          advance();
          return;
        }
        const board = one('.scoreboard');
        screenFading = true;
        board.classList.add('monitor-fading');
        setTimeout(() => {
          advance();
          board.classList.remove('monitor-fading');
          setTimeout(() => {
            screenFading = false;
          }, 300);
        }, 300);
      };
      if (enabled && one('.scoreboard')) {
        one('[data-monitor-tools]').hidden = false;
        one('[data-monitor-prev]').addEventListener('click', () => changeScreenPage(-1));
        one('[data-monitor-next]').addEventListener('click', () => changeScreenPage(1));
        one('[data-monitor-rotate]').addEventListener('click', (event) => {
          rotating = !rotating;
          event.currentTarget.setAttribute('aria-pressed', String(rotating));
          event.currentTarget.textContent = `Rotate: ${rotating ? 'on' : 'off'}`;
        });
        one('[data-fullscreen]').addEventListener('click', async (event) => {
          try {
            if (document.fullscreenElement) await document.exitFullscreen();
            else await document.documentElement.requestFullscreen();
          } catch {
            event.currentTarget.textContent = 'Use browser fullscreen';
          }
        });
        addEventListener('resize', layoutMonitor);
        setInterval(() => {
          if (!rotating || document.hidden || screenPages < 2) return;
          changeScreenPage(1);
        }, 12000);
        requestAnimationFrame(layoutMonitor);
      }

      return { layout: layoutMonitor };
    },
  };
})();
