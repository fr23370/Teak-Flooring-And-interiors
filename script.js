const heroVisual = document.getElementById('heroVisual');
const slideIndex = document.getElementById('slideIndex');
const slideTitle = document.getElementById('slideTitle');

const slides = [
  {
    image: "url('https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1400&q=85')",
    label: 'A warm, thoughtfully renovated living space',
    number: '01 / 04'
  },
  {
    image: "url('https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1200&q=85')",
    label: 'Considered finishes for a welcoming home',
    number: '02 / 04'
  },
  {
    image: "url('https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?auto=format&fit=crop&w=900&q=85')",
    label: 'Bright spaces, carefully refreshed',
    number: '03 / 04'
  },
  {
    image: "url('https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?auto=format&fit=crop&w=900&q=85')",
    label: 'Interior details made to feel at home',
    number: '04 / 04'
  }
];

let slidePosition = 0;

function renderSlide(index) {
  if (!heroVisual || !slideIndex || !slideTitle) return;

  const current = slides[index];
  heroVisual.style.backgroundImage = `linear-gradient(180deg, transparent 68%, rgba(25, 27, 21, 0.42)), ${current.image}`;
  heroVisual.setAttribute('aria-label', current.label);
  slideIndex.textContent = current.number;
  slideTitle.textContent = current.label;
}

function nextSlide() {
  slidePosition = (slidePosition + 1) % slides.length;
  renderSlide(slidePosition);
}

if (heroVisual) {
  renderSlide(slidePosition);
  setInterval(nextSlide, 5000);
}

const header = document.querySelector('.site-header');
const updateHeaderState = () => {
  if (!header) return;
  header.classList.toggle('is-scrolled', window.scrollY > 18);
};

updateHeaderState();
window.addEventListener('scroll', updateHeaderState, { passive: true });

const revealItems = document.querySelectorAll('.reveal-on-scroll, .collection-card, .service-item, .stat-item');

if ('IntersectionObserver' in window) {
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  revealItems.forEach((item) => revealObserver.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add('visible'));
}

const counters = document.querySelectorAll('[data-counter]');

if (counters.length && 'IntersectionObserver' in window) {
  const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;

      const el = entry.target;
      const target = Number(el.dataset.counter || 0);
      const suffix = el.dataset.suffix || '';
      const prefix = el.dataset.prefix || '';
      let current = 0;
      const step = Math.max(1, Math.ceil(target / 35));

      const timer = setInterval(() => {
        current += step;
        if (current >= target) {
          current = target;
          clearInterval(timer);
        }
        el.textContent = `${prefix}${current}${suffix}`;
      }, 35);

      counterObserver.unobserve(el);
    });
  }, { threshold: 0.5 });

  counters.forEach((counter) => counterObserver.observe(counter));
}

const gallery = document.querySelector('[data-project-gallery]');

if (gallery) {
  const projectGrid = gallery.querySelector('[data-project-grid]');
  const galleryStatus = gallery.querySelector('[data-gallery-status]');
  const filterButtons = [...gallery.querySelectorAll('[data-project-filter]')];
  const displayLimit = Number(gallery.dataset.limit || 0);
  let projects = [];
  let activeCategory = 'All';

  function renderProjects() {
    const filtered = activeCategory === 'All'
      ? projects
      : projects.filter((project) => project.category === activeCategory);
    const visible = displayLimit && activeCategory === 'All'
      ? filtered.slice(0, displayLimit)
      : filtered;

    projectGrid.replaceChildren();
    visible.forEach((project) => {
      const card = document.createElement('article');
      card.className = 'project-card reveal-on-scroll visible';
      const imageFrame = document.createElement('div');
      imageFrame.className = 'project-image-frame';
      const image = document.createElement('img');
      image.src = project.image;
      image.alt = project.alt || project.title;
      image.loading = 'lazy';
      image.addEventListener('error', () => {
        imageFrame.classList.add('project-image-unavailable');
        image.removeAttribute('src');
        image.alt = 'Project image unavailable';
      }, { once: true });
      imageFrame.append(image);

      if (project.placeholder) {
        const badge = document.createElement('span');
        badge.className = 'project-placeholder';
        badge.textContent = 'Design inspiration';
        imageFrame.append(badge);
      }

      const details = document.createElement('div');
      details.className = 'project-card-copy';
      const category = document.createElement('p');
      category.className = 'eyebrow';
      category.textContent = project.category;
      const title = document.createElement('h3');
      title.textContent = project.title;
      const description = document.createElement('p');
      description.textContent = project.description || '';
      details.append(category, title, description);
      card.append(imageFrame, details);
      projectGrid.append(card);
    });

    galleryStatus.textContent = visible.length
      ? `${visible.length} ${visible.length === 1 ? 'project' : 'projects'} shown`
      : `No projects in ${activeCategory} yet. Please check back soon.`;
  }

  filterButtons.forEach((button) => {
    button.addEventListener('click', () => {
      activeCategory = button.dataset.projectFilter;
      filterButtons.forEach((filter) => {
        const selected = filter === button;
        filter.classList.toggle('is-active', selected);
        filter.setAttribute('aria-pressed', String(selected));
      });
      renderProjects();
    });
  });

  fetch('/api/projects')
    .then((response) => {
      if (!response.ok) throw new Error('Project gallery is temporarily unavailable.');
      return response.json();
    })
    .then((data) => {
      if (!Array.isArray(data)) throw new Error('Project gallery data is invalid.');
      projects = data;
      renderProjects();
    })
    .catch((error) => {
      galleryStatus.textContent = `${error.message} Please refresh the page or contact us to see our work.`;
    });
}
