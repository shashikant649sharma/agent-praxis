/**
 * Agent Praxis - Interactive Enhancements
 */
document.addEventListener('DOMContentLoaded', () => {
  const header = document.getElementById('site-header');
  const artwork = document.querySelector('.hero-artwork-bg');

  // Subtle header shadow on scroll
  window.addEventListener('scroll', () => {
    if (window.scrollY > 20) {
      header.style.boxShadow = '0 4px 20px rgba(22, 50, 197, 0.08)';
    } else {
      header.style.boxShadow = 'none';
    }
  });

  // Gentle subtle parallax on artwork on mouse move for depth
  if (window.matchMedia('(hover: hover)').matches && artwork) {
    document.addEventListener('mousemove', (e) => {
      const { innerWidth, innerHeight } = window;
      const xPercent = (e.clientX / innerWidth - 0.5) * 12;
      const yPercent = (e.clientY / innerHeight - 0.5) * 12;
      
      artwork.style.transform = `translate3d(${-xPercent}px, ${-yPercent}px, 0) scale(1.02)`;
    });
  }

  // Smooth scroll for downward arrow
  const scrollCue = document.querySelector('.hero-scroll-cue');
  if (scrollCue) {
    scrollCue.addEventListener('click', (e) => {
      e.preventDefault();
      window.scrollTo({
        top: window.innerHeight * 0.7,
        behavior: 'smooth'
      });
    });
  }

  // Interactive Expandable Worlds Accordion
  const worldRows = document.querySelectorAll('.sic-world-row');
  worldRows.forEach(row => {
    const headerRow = row.querySelector('.world-header-row');
    if (!headerRow) return;

    const toggleRow = () => {
      const isAlreadyOpen = row.classList.contains('is-open');
      
      // Close other rows for clean single-focus accordion experience
      worldRows.forEach(otherRow => {
        if (otherRow !== row) {
          otherRow.classList.remove('is-open');
          const otherHeader = otherRow.querySelector('.world-header-row');
          if (otherHeader) otherHeader.setAttribute('aria-expanded', 'false');
        }
      });

      // Toggle current row
      row.classList.toggle('is-open', !isAlreadyOpen);
      headerRow.setAttribute('aria-expanded', !isAlreadyOpen ? 'true' : 'false');
    };

    headerRow.addEventListener('click', (e) => {
      // Avoid intercepting clicks if user specifically clicks a link
      if (e.target.closest('a')) return;
      toggleRow();
    });

    headerRow.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleRow();
      }
    });
  });
});
