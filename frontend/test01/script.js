const topButton = document.querySelector('.top-button');
const navLinks  = [...document.querySelectorAll('.nav-menu a')];

function onScroll() {
  topButton.classList.toggle('is-visible', window.scrollY > 420);

  const y = window.scrollY + 120;
  let current = null;
  for (const link of navLinks) {
    const href = link.getAttribute('href');
    if (!href || !href.startsWith('#')) continue;
    const target = document.querySelector(href);
    if (target && target.offsetTop <= y) current = link;
  }
  navLinks.forEach(l => l.classList.remove('active'));
  if (current) current.classList.add('active');
}

window.addEventListener('scroll', onScroll);
topButton.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

onScroll();
