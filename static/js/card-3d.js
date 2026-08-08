/**
 * SmartReco 3D Card Effects
 * Interactive 3D tilt, magnetic hover, and depth effects for cards
 */
(function() {
    'use strict';

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) return;

    const cards = [];
    let rafId = null;

    function initCard3D() {
        const cardElements = document.querySelectorAll('.product-card, .glass-card, [data-card-3d], .reco-widget');
        
        cardElements.forEach(card => {
            if (card.dataset.card3dInitialized) return;
            card.dataset.card3dInitialized = 'true';
            
            setupCard3D(card);
            cards.push(card);
        });

        if (cards.length > 0) {
            startRenderLoop();
        }
    }

    function setupCard3D(card) {
        card.style.transformStyle = 'preserve-3d';
        card.style.transition = 'transform 0.1s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
        
        const innerElements = card.querySelectorAll('.card-title, .card-desc, .card-badge, .rating-tag, .tag-pill, .price-tag, .btn, .card-top-header, .card-footer, .card-tags');
        innerElements.forEach((el, index) => {
            el.style.transform = `translateZ(${10 + index * 5}px)`;
            el.style.transition = 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
        });

        const shine = document.createElement('div');
        shine.className = 'card-shine';
        shine.style.cssText = `
            position: absolute;
            inset: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0) 50%);
            border-radius: inherit;
            opacity: 0;
            pointer-events: none;
            z-index: 10;
            transition: opacity 0.3s ease;
        `;
        card.style.position = 'relative';
        card.appendChild(shine);
        card._shine = shine;

        card._cardData = {
            rotateX: 0,
            rotateY: 0,
            targetRotateX: 0,
            targetRotateY: 0,
            shineX: 50,
            shineY: 50
        };

        card.addEventListener('mousemove', handleMouseMove);
        card.addEventListener('mouseleave', handleMouseLeave);
        card.addEventListener('mouseenter', handleMouseEnter);
    }

    function handleMouseMove(e) {
        const card = e.currentTarget;
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        
        const rotateY = ((x - centerX) / centerX) * 8;
        const rotateX = -((y - centerY) / centerY) * 8;
        
        card._cardData.targetRotateX = rotateX;
        card._cardData.targetRotateY = rotateY;
        card._cardData.shineX = (x / rect.width) * 100;
        card._cardData.shineY = (y / rect.height) * 100;
    }

    function handleMouseEnter(e) {
        const card = e.currentTarget;
        card._cardData.isHovered = true;
        if (card._shine) {
            card._shine.style.opacity = '1';
        }
        card.style.boxShadow = '0 32px 80px rgba(0, 0, 0, 0.6), 0 0 60px rgba(99, 102, 241, 0.4)';
        card.style.zIndex = '10';
    }

    function handleMouseLeave(e) {
        const card = e.currentTarget;
        card._cardData.isHovered = false;
        card._cardData.targetRotateX = 0;
        card._cardData.targetRotateY = 0;
        
        if (card._shine) {
            card._shine.style.opacity = '0';
        }
        card.style.boxShadow = '';
        card.style.zIndex = '';
    }

    function updateCards() {
        cards.forEach(card => {
            const data = card._cardData;
            if (!data) return;

            data.rotateX += (data.targetRotateX - data.rotateX) * 0.15;
            data.rotateY += (data.targetRotateY - data.rotateY) * 0.15;

            if (Math.abs(data.rotateX) > 0.01 || Math.abs(data.rotateY) > 0.01) {
                card.style.transform = `perspective(1000px) rotateX(${data.rotateX}deg) rotateY(${data.rotateY}deg) scale3d(1.01, 1.01, 1.01)`;
            } else {
                card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0)';
            }

            if (card._shine) {
                card._shine.style.background = `radial-gradient(ellipse at ${data.shineX}% ${data.shineY}%, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0) 60%)`;
            }

            const innerElements = card.querySelectorAll('[style*="translateZ"]');
            innerElements.forEach((el, index) => {
                const depth = 10 + index * 5;
                const parallaxX = data.rotateY * (depth / 10);
                const parallaxY = data.rotateX * (depth / 10);
                el.style.transform = `translateZ(${depth}px) translateX(${-parallaxX}px) translateY(${-parallaxY}px)`;
            });
        });
    }

    function startRenderLoop() {
        function render() {
            updateCards();
            rafId = requestAnimationFrame(render);
        }
        render();
    }

    function initMagneticButtons() {
        const buttons = document.querySelectorAll('.btn[data-magnetic], .chip-btn, [data-magnetic]');
        
        buttons.forEach(btn => {
            btn.addEventListener('mousemove', (e) => {
                const rect = btn.getBoundingClientRect();
                const x = e.clientX - rect.left - rect.width / 2;
                const y = e.clientY - rect.top - rect.height / 2;
                
                btn.style.transform = `translate(${x * 0.2}px, ${y * 0.2}px)`;
                btn.style.transition = 'transform 0.1s cubic-bezier(0.16, 1, 0.3, 1)';
            });

            btn.addEventListener('mouseleave', () => {
                btn.style.transform = 'translate(0, 0)';
                btn.style.transition = 'transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)';
            });
        });
    }

    function initRippleEffect() {
        const rippleElements = document.querySelectorAll('.btn, .chip-btn, .nav-link, [data-ripple]');
        
        rippleElements.forEach(el => {
            el.addEventListener('click', function(e) {
                if (this.querySelector('.ripple')) return;
                
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;
                
                const ripple = document.createElement('span');
                ripple.className = 'ripple';
                ripple.style.cssText = `
                    position: absolute;
                    width: ${size}px;
                    height: ${size}px;
                    left: ${x}px;
                    top: ${y}px;
                    background: rgba(255, 255, 255, 0.3);
                    border-radius: 50%;
                    transform: scale(0);
                    animation: rippleEffect 0.6s cubic-bezier(0.16, 1, 0.3, 1);
                    pointer-events: none;
                    z-index: 1;
                `;
                
                this.style.position = 'relative';
                this.style.overflow = 'hidden';
                this.appendChild(ripple);
                
                setTimeout(() => ripple.remove(), 600);
            });
        });
    }

    function init() {
        initCard3D();
        initMagneticButtons();
        initRippleEffect();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    const style = document.createElement('style');
    style.textContent = `
        @keyframes rippleEffect {
            to {
                transform: scale(2.5);
                opacity: 0;
            }
        }
        
        .product-card, .glass-card, [data-card-3d] {
            will-change: transform, box-shadow;
        }
    `;
    document.head.appendChild(style);

    window.Card3D = {
        init,
        refresh: () => {
            cards.length = 0;
            initCard3D();
        }
    };
})();