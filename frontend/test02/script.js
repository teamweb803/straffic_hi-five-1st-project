const slides = [...document.querySelectorAll('[data-hero-slide]')];
const dots = [...document.querySelectorAll('[data-hero-dot]')];
const prevButton = document.querySelector('[data-hero-prev]');
const nextButton = document.querySelector('[data-hero-next]');
const hero = document.querySelector('.hero');

if (slides.length) {
  let activeIndex = 0;
  let timer = null;

  const showSlide = (index) => {
    activeIndex = (index + slides.length) % slides.length;

    slides.forEach((slide, slideIndex) => {
      slide.classList.toggle('is-active', slideIndex === activeIndex);
    });

    dots.forEach((dot, dotIndex) => {
      dot.classList.toggle('is-active', dotIndex === activeIndex);
    });
  };

  const startAutoPlay = () => {
    stopAutoPlay();
    timer = window.setInterval(() => showSlide(activeIndex + 1), 4500);
  };

  const stopAutoPlay = () => {
    if (timer) {
      window.clearInterval(timer);
      timer = null;
    }
  };

  dots.forEach((dot) => {
    dot.addEventListener('click', () => {
      showSlide(Number(dot.dataset.heroDot));
      startAutoPlay();
    });
  });

  prevButton?.addEventListener('click', () => {
    showSlide(activeIndex - 1);
    startAutoPlay();
  });

  nextButton?.addEventListener('click', () => {
    showSlide(activeIndex + 1);
    startAutoPlay();
  });

  hero?.addEventListener('mouseenter', stopAutoPlay);
  hero?.addEventListener('mouseleave', startAutoPlay);

  showSlide(0);
  startAutoPlay();
}
