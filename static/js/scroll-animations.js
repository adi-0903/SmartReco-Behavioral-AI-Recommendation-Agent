/**
 * SmartReco Scroll Animations using GSAP ScrollTrigger
 * Reveal animations, parallax effects, and scroll-based interactions
 */
(function() {
    'use strict';

    if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') {
        console.warn('GSAP or ScrollTrigger not loaded, scroll animations disabled');
        return;
    }

    gsap.registerPlugin(ScrollTrigger);

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) return;

    function initRevealAnimations() {
        const revealElements = document.querySelectorAll('.reveal, .product-card, .hero-banner, .reco-widget, .section-header, .filter-bar, .data-table, .glass-card');
        
        revealElements.forEach((el, index) => {
            if (el.classList.contains('reveal-initialized')) return;
            el.classList.add('reveal-initialized');
            
            const delay = el.dataset.revealDelay || (index % 6) * 0.1;
            const direction = el.dataset.revealDirection || 'up';
            
            let yValue = 50;
            if (direction === 'left') yValue = 0;
            if (direction === 'right') yValue = 0;
            
            gsap.fromTo(el, 
                { 
                    opacity: 0, 
                    y: direction === 'up' ? yValue : 0,
                    x: direction === 'left' ? -yValue : direction === 'right' ? yValue : 0,
                    scale: el.classList.contains('product-card') ? 0.95 : 1
                },
                {
                    opacity: 1,
                    y: 0,
                    x: 0,
                    scale: 1,
                    duration: 0.8,
                    delay: delay,
                    ease: 'power3.out',
                    scrollTrigger: {
                        trigger: el,
                        start: 'top 85%',
                        end: 'bottom 20%',
                        toggleActions: 'play none none reverse',
                        once: false
                    }
                }
            );
        });
    }

    function initHeroParallax() {
        const hero = document.querySelector('.hero-banner');
        if (!hero) return;

        gsap.to(hero, {
            yPercent: 30,
            ease: 'none',
            scrollTrigger: {
                trigger: hero,
                start: 'top top',
                end: 'bottom top',
                scrub: 1
            }
        });

        const heroTitle = hero.querySelector('.hero-title');
        const heroSubtitle = hero.querySelector('.hero-subtitle');
        const heroActions = hero.querySelector('.hero-actions');

        if (heroTitle) {
            gsap.fromTo(heroTitle, { y: 0 }, {
                yPercent: -50,
                ease: 'none',
                scrollTrigger: {
                    trigger: hero,
                    start: 'top top',
                    end: 'bottom top',
                    scrub: 1
                }
            });
        }
    }

    function initNavbarScroll() {
        const navbar = document.querySelector('.navbar');
        if (!navbar) return;

        ScrollTrigger.create({
            trigger: 'body',
            start: 'top -80',
            end: 'bottom bottom',
            onEnter: () => navbar.classList.add('scrolled'),
            onLeaveBack: () => navbar.classList.remove('scrolled')
        });
    }

    function initProductCardHover() {
        const cards = document.querySelectorAll('.product-card');
        
        cards.forEach(card => {
            card.addEventListener('mouseenter', () => {
                gsap.to(card, {
                    y: -8,
                    scale: 1.01,
                    boxShadow: '0 24px 64px rgba(0, 0, 0, 0.6), 0 0 40px rgba(99, 102, 241, 0.3)',
                    duration: 0.3,
                    ease: 'power2.out'
                });
            });

            card.addEventListener('mouseleave', () => {
                gsap.to(card, {
                    y: 0,
                    scale: 1,
                    boxShadow: 'none',
                    duration: 0.4,
                    ease: 'power2.out'
                });
            });
        });
    }

    function initStaggeredList() {
        const lists = document.querySelectorAll('[data-stagger]');
        
        lists.forEach(list => {
            const items = list.querySelectorAll('[data-stagger-item]');
            if (items.length === 0) return;

            gsap.fromTo(items, 
                { opacity: 0, y: 30 },
                {
                    opacity: 1,
                    y: 0,
                    duration: 0.6,
                    stagger: 0.1,
                    ease: 'power3.out',
                    scrollTrigger: {
                        trigger: list,
                        start: 'top 80%',
                        toggleActions: 'play none none reverse'
                    }
                }
            );
        });
    }

    function initCounterAnimations() {
        const counters = document.querySelectorAll('[data-counter]');
        
        counters.forEach(counter => {
            const target = parseInt(counter.dataset.counter, 10);
            const duration = parseFloat(counter.dataset.duration) || 2;
            
            gsap.fromTo({ value: 0 }, { value: target }, {
                duration: duration,
                ease: 'power2.out',
                scrollTrigger: {
                    trigger: counter,
                    start: 'top 85%',
                    toggleActions: 'play none none none'
                },
                onUpdate: function() {
                    counter.textContent = Math.round(this.targets()[0].value).toLocaleString();
                }
            });
        });
    }

    function initGradientTextAnimation() {
        const gradientTexts = document.querySelectorAll('.gradient-text');
        
        gradientTexts.forEach(text => {
            gsap.to(text, {
                backgroundPosition: '200% 50%',
                ease: 'none',
                duration: 4,
                repeat: -1,
                yoyo: true
            });
        });
    }

    function initMagneticButtons() {
        const magneticElements = document.querySelectorAll('[data-magnetic]');
        
        magneticElements.forEach(el => {
            el.addEventListener('mousemove', (e) => {
                const rect = el.getBoundingClientRect();
                const x = e.clientX - rect.left - rect.width / 2;
                const y = e.clientY - rect.top - rect.height / 2;
                
                gsap.to(el, {
                    x: x * 0.3,
                    y: y * 0.3,
                    duration: 0.3,
                    ease: 'power2.out'
                });
            });

            el.addEventListener('mouseleave', () => {
                gsap.to(el, {
                    x: 0,
                    y: 0,
                    duration: 0.5,
                    ease: 'elastic.out(1, 0.5)'
                });
            });
        });
    }

    function initFloatAnimation() {
        const floatElements = document.querySelectorAll('[data-float]');
        
        floatElements.forEach((el, index) => {
            const intensity = parseFloat(el.dataset.float) || 10;
            const duration = parseFloat(el.dataset.floatDuration) || 3;
            
            gsap.to(el, {
                y: -intensity,
                duration: duration,
                ease: 'sine.inOut',
                yoyo: true,
                repeat: -1,
                delay: index * 0.2
            });
        });
    }

    function initScrollProgress() {
        const progressBar = document.querySelector('[data-scroll-progress]');
        if (!progressBar) return;

        gsap.to(progressBar, {
            scaleX: 1,
            ease: 'none',
            scrollTrigger: {
                trigger: 'body',
                start: 'top top',
                end: 'bottom bottom',
                scrub: 0.1
            }
        });
    }

    function initPinSections() {
        const pinSections = document.querySelectorAll('[data-pin]');
        
        pinSections.forEach(section => {
            const pinContent = section.querySelector('[data-pin-content]');
            if (!pinContent) return;

            ScrollTrigger.create({
                trigger: section,
                start: 'top top',
                end: 'bottom bottom',
                pin: pinContent,
                pinSpacing: false
            });
        });
    }

    function initImageParallax() {
        const parallaxImages = document.querySelectorAll('[data-parallax]');
        
        parallaxImages.forEach(img => {
            const speed = parseFloat(img.dataset.parallax) || 0.5;
            
            gsap.to(img, {
                yPercent: -50 * speed,
                ease: 'none',
                scrollTrigger: {
                    trigger: img,
                    start: 'top bottom',
                    end: 'bottom top',
                    scrub: true
                }
            });
        });
    }

    function initTextReveal() {
        const textElements = document.querySelectorAll('[data-text-reveal]');
        
        textElements.forEach(el => {
            const text = el.textContent;
            el.innerHTML = '';
            
            const words = text.split(' ');
            words.forEach((word, i) => {
                const span = document.createElement('span');
                span.style.display = 'inline-block';
                span.style.opacity = '0';
                span.style.transform = 'translateY(100%)';
                span.textContent = word + (i < words.length - 1 ? ' ' : '');
                el.appendChild(span);
            });

            const spans = el.querySelectorAll('span');
            gsap.to(spans, {
                opacity: 1,
                y: 0,
                duration: 0.8,
                stagger: 0.05,
                ease: 'power3.out',
                scrollTrigger: {
                    trigger: el,
                    start: 'top 85%',
                    toggleActions: 'play none none reverse'
                }
            });
        });
    }

    function init() {
        initRevealAnimations();
        initHeroParallax();
        initNavbarScroll();
        initProductCardHover();
        initStaggeredList();
        initCounterAnimations();
        initGradientTextAnimation();
        initMagneticButtons();
        initFloatAnimation();
        initScrollProgress();
        initPinSections();
        initImageParallax();
        initTextReveal();

        ScrollTrigger.refresh();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.SmartRecoScroll = {
        refresh: () => ScrollTrigger.refresh(),
        kill: () => ScrollTrigger.getAll().forEach(t => t.kill()),
        init
    };
})();