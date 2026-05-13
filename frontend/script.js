const topButton = document.querySelector('.top-button');
const compareButton = document.querySelector('.compare-button');
const referenceLayer = document.querySelector('.reference-layer');
const navLinks = [...document.querySelectorAll('.nav-menu a')];

function updateScrollState() {
  topButton.classList.toggle('is-visible', window.scrollY > 420);

  const y = window.scrollY + 120;
  let current = null;

  for (const link of navLinks) {
    const target = document.querySelector(link.getAttribute('href'));
    if (target && target.offsetTop <= y) current = link;
  }

  navLinks.forEach(link => link.classList.remove('active'));
  if (current) current.classList.add('active');
}

window.addEventListener('scroll', updateScrollState);
topButton.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

compareButton.addEventListener('click', () => {
  referenceLayer.classList.toggle('is-visible');
});

window.addEventListener('keydown', (event) => {
  if (event.key.toLowerCase() === 'r') {
    referenceLayer.classList.toggle('is-visible');
  }
});

updateScrollState();
