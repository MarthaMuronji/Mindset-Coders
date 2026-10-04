document.addEventListener('DOMContentLoaded', function () {
    const navCollapse = document.querySelector('.nav-collapse');
    if (navCollapse) {
        navCollapse.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () {
                navCollapse.classList.remove('open');
            });
        });
    }

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const revealEls = document.querySelectorAll('.reveal');

    if (prefersReducedMotion) {
        revealEls.forEach(function (el) {
            el.classList.add('is-visible');
        });
    } else {
        const revealObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    revealObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });

        revealEls.forEach(function (el) {
            revealObserver.observe(el);
        });
    }

    const counters = document.querySelectorAll('.stat-number[data-count]');

    function setFinalCount(el) {
        const target = parseInt(el.dataset.count, 10);
        const suffix = el.dataset.suffix || '';
        el.textContent = target.toLocaleString() + suffix;
    }

    if (prefersReducedMotion) {
        counters.forEach(setFinalCount);
    } else {
        const countObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    animateCount(entry.target);
                    countObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });

        counters.forEach(function (el) {
            countObserver.observe(el);
        });
    }

    function animateCount(el) {
        const target = parseInt(el.dataset.count, 10);
        const suffix = el.dataset.suffix || '';
        const duration = 1200;
        const start = performance.now();

        function step(now) {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.floor(eased * target);
            el.textContent = current.toLocaleString() + suffix;
            if (progress < 1) {
                requestAnimationFrame(step);
            } else {
                el.textContent = target.toLocaleString() + suffix;
            }
        }
        requestAnimationFrame(step);
    }

});
