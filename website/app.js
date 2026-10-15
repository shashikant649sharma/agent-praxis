/**
 * Agent Praxis - Literary & Artistic Website Script
 * Powers the Empirical Ledger, Trajectory Audit Folio, and Filtration
 */

document.addEventListener('DOMContentLoaded', () => {
  initLeaderboard();
  initPathModal();
  initSmoothScroll();
});

let currentFilter = 'all';

function initLeaderboard() {
  const tableBody = document.getElementById('leaderboard-body');
  const filterButtons = document.querySelectorAll('.filter-btn');
  const searchInput = document.getElementById('model-search');

  if (!window.AGENT_PRAXIS_BENCHMARK_DATA || !Array.isArray(window.AGENT_PRAXIS_BENCHMARK_DATA)) {
    console.warn('Empirical benchmark ledger data not loaded.');
    return;
  }

  function renderTable() {
    const rawData = window.AGENT_PRAXIS_BENCHMARK_DATA;
    const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

    const filtered = rawData.filter(item => {
      const matchesEnv = currentFilter === 'all' || item.environment.toLowerCase() === currentFilter.toLowerCase();
      const matchesSearch = !query || 
        item.model.toLowerCase().includes(query) || 
        item.environment.toLowerCase().includes(query);
      return matchesEnv && matchesSearch;
    });

    tableBody.innerHTML = '';

    if (filtered.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 48px; color: var(--ink-muted); font-style: italic;">No trials recorded matching the specified criteria.</td></tr>`;
      return;
    }

    filtered.forEach((run, index) => {
      const tr = document.createElement('tr');
      const scorePct = Math.round((run.score || 0) * 100);

      const statusBadge = run.task_success
        ? `<span class="badge-seal pass">Pass</span>`
        : `<span class="badge-seal fail">Incomplete</span>`;

      const complianceBadge = run.constraint_compliance
        ? `<span class="badge-seal pass">Compliant</span>`
        : `<span class="badge-seal fail">Breached</span>`;

      const trapBadge = run.fell_for_trap
        ? `<span class="badge-seal trap">Fell For Trap</span>`
        : `<span class="badge-seal pass">Resisted</span>`;

      tr.innerHTML = `
        <td>
          <div class="model-name">${escapeHtml(run.model)}</div>
          <span class="seed-sub">Seed: ${run.seed} • ${run.steps} Steps</span>
        </td>
        <td>
          <strong style="color: var(--cobalt-primary); font-family: var(--font-serif-display); font-size: 0.95rem;">
            ${formatEnvName(run.environment)}
          </strong>
        </td>
        <td>
          <div class="score-display">${(run.score || 0).toFixed(3)}</div>
          <div class="score-bar-bg">
            <div class="score-bar-fill" style="width: ${scorePct}%;"></div>
          </div>
        </td>
        <td>${statusBadge}</td>
        <td>${complianceBadge}</td>
        <td>${trapBadge}</td>
        <td>
          <button class="btn-trajectory" data-index="${index}">Audit Trajectory</button>
        </td>
      `;
      tableBody.appendChild(tr);
    });

    // Attach click listeners to all trajectory audit buttons
    document.querySelectorAll('.btn-trajectory').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.getAttribute('data-index'), 10);
        showPathModal(filtered[idx]);
      });
    });
  }

  filterButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      filterButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.getAttribute('data-filter');
      renderTable();
    });
  });

  if (searchInput) {
    searchInput.addEventListener('input', renderTable);
  }

  renderTable();
}

/* -------------------------------------------------------------------------
   Trajectory Audit Folio Modal
   ------------------------------------------------------------------------- */
function initPathModal() {
  const modal = document.getElementById('path-modal');
  const closeBtn = document.getElementById('modal-close-btn');

  if (closeBtn && modal) {
    closeBtn.addEventListener('click', () => {
      modal.classList.remove('active');
    });

    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('active');
      }
    });
  }
}

function showPathModal(run) {
  const modal = document.getElementById('path-modal');
  const title = document.getElementById('modal-title');
  const desc = document.getElementById('modal-desc');
  const list = document.getElementById('modal-step-list');

  if (!modal || !run) return;

  title.textContent = `${run.model} — ${formatEnvName(run.environment)}`;
  desc.innerHTML = `Final Evidence Score: <strong>${(run.score || 0).toFixed(3)}</strong> &bull; Total Steps: ${run.steps} &bull; Trap Fall: <em>${run.fell_for_trap ? 'Affirmative' : 'Resisted'}</em> &bull; Compliance: <em>${run.constraint_compliance ? 'Sustained' : 'Violated'}</em>`;

  list.innerHTML = '';
  if (Array.isArray(run.path) && run.path.length > 0) {
    run.path.forEach((step, i) => {
      const item = document.createElement('li');
      item.className = 'step-ledger-item';
      item.innerHTML = `
        <span class="step-num">ACT ${i + 1}</span>
        <span style="color: var(--ink-primary); font-weight: 500;"><code>${escapeHtml(step)}</code></span>
      `;
      list.appendChild(item);
    });
  } else {
    list.innerHTML = `<li class="step-ledger-item">No granular action entries recorded for this candidate trial.</li>`;
  }

  modal.classList.add('active');
}

function formatEnvName(env) {
  switch (env.toLowerCase()) {
    case '1984': return 'Nineteen Eighty-Four';
    case 'the-trial': return 'The Trial';
    case 'dorian-gray': return 'The Picture of Dorian Gray';
    case 'catch-22': return 'Catch-22';
    case 'frankenstein': return 'Frankenstein';
    case 'metamorphosis': return 'Metamorphosis';
    default: return env;
  }
}

function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
      }
    });
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
