/**
 * SmartReco Theme Toggle
 * Dark/Light mode with persistence and system preference detection
 */
(function() {
    'use strict';

    const THEME_KEY = 'smartreco-theme';
    const THEME_ATTR = 'data-theme';
    const DARK = 'dark';
    const LIGHT = 'light';

    let currentTheme = DARK;
    let mediaQuery = null;

    function getInitialTheme() {
        const stored = localStorage.getItem(THEME_KEY);
        if (stored) return stored;

        if (window.matchMedia('(prefers-color-scheme: light)').matches) {
            return LIGHT;
        }
        return DARK;
    }

    function applyTheme(theme) {
        currentTheme = theme;
        document.documentElement.setAttribute(THEME_ATTR, theme);
        localStorage.setItem(THEME_KEY, theme);
        
        updateMetaThemeColor(theme);
        dispatchThemeChangeEvent(theme);
    }

    function updateMetaThemeColor(theme) {
        let metaThemeColor = document.querySelector('meta[name="theme-color"]');
        if (!metaThemeColor) {
            metaThemeColor = document.createElement('meta');
            metaThemeColor.name = 'theme-color';
            document.head.appendChild(metaThemeColor);
        }
        
        const colors = {
            dark: '#0b0f19',
            light: '#f8fafc'
        };
        metaThemeColor.content = colors[theme] || colors.dark;
    }

    function dispatchThemeChangeEvent(theme) {
        const event = new CustomEvent('themechange', {
            detail: { theme, previousTheme: currentTheme === theme ? null : (theme === DARK ? LIGHT : DARK) }
        });
        window.dispatchEvent(event);
    }

    function toggleTheme() {
        const newTheme = currentTheme === DARK ? LIGHT : DARK;
        applyTheme(newTheme);
        animateThemeToggle(newTheme);
    }

    function animateThemeToggle(theme) {
        const toggleBtn = document.getElementById('themeToggle');
        if (!toggleBtn) return;

        toggleBtn.style.transform = 'scale(0.8) rotate(90deg)';
        toggleBtn.style.transition = 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
        
        setTimeout(() => {
            toggleBtn.style.transform = 'scale(1) rotate(0deg)';
        }, 150);

        const ripple = document.createElement('div');
        ripple.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: ${theme === LIGHT ? 'rgba(255,255,255,0.3)' : 'rgba(99,102,241,0.3)'};
            transform: translate(-50%, -50%);
            pointer-events: none;
            z-index: 9999;
            animation: themeRipple 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        `;
        document.body.appendChild(ripple);
        setTimeout(() => ripple.remove(), 600);
    }

    function initThemeToggle() {
        const toggleBtn = document.getElementById('themeToggle');
        if (!toggleBtn) return;

        toggleBtn.addEventListener('click', toggleTheme);
        toggleBtn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleTheme();
            }
        });
    }

    function initSystemPreferenceListener() {
        mediaQuery = window.matchMedia('(prefers-color-scheme: light)');
        mediaQuery.addEventListener('change', (e) => {
            const stored = localStorage.getItem(THEME_KEY);
            if (!stored) {
                applyTheme(e.matches ? LIGHT : DARK);
            }
        });
    }

    function init() {
        const theme = getInitialTheme();
        applyTheme(theme);
        initThemeToggle();
        initSystemPreferenceListener();

        document.addEventListener('keydown', (e) => {
            if (e.key === 't' && (e.ctrlKey || e.metaKey) && e.shiftKey) {
                e.preventDefault();
                toggleTheme();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    const style = document.createElement('style');
    style.textContent = `
        @keyframes themeRipple {
            to {
                width: 200vmax;
                height: 200vmax;
                opacity: 0;
            }
        }
        
        [data-theme="light"] {
            --bg-deep: #f8fafc;
            --bg-dark: #ffffff;
            --bg-card: rgba(255, 255, 255, 0.8);
            --bg-card-strong: rgba(255, 255, 255, 0.95);
            --bg-card-hover: rgba(241, 245, 249, 0.9);
            --bg-glass: rgba(255, 255, 255, 0.6);
            --bg-glass-strong: rgba(255, 255, 255, 0.85);
            
            --border-subtle: rgba(15, 23, 42, 0.05);
            --border-color: rgba(15, 23, 42, 0.1);
            --border-accent: rgba(99, 102, 241, 0.4);
            
            --text-main: #0f172a;
            --text-bright: #020617;
            --text-muted: #475569;
            --text-dim: #94a3b8;
            --text-subtle: #cbd5e1;
            
            --shadow-xs: 0 1px 3px rgba(15, 23, 42, 0.08);
            --shadow-sm: 0 4px 12px rgba(15, 23, 42, 0.1);
            --shadow-md: 0 8px 24px rgba(15, 23, 42, 0.12);
            --shadow-lg: 0 16px 48px rgba(15, 23, 42, 0.15);
            --shadow-xl: 0 24px 64px rgba(15, 23, 42, 0.18);
        }
        
        [data-theme="light"] body {
            background-color: var(--bg-deep);
            background-image: 
                radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99, 102, 241, 0.08), transparent),
                radial-gradient(ellipse 60% 40% at 100% 100%, rgba(236, 72, 153, 0.05), transparent),
                radial-gradient(ellipse 50% 30% at 0% 0%, rgba(56, 189, 248, 0.04), transparent);
        }
        
        [data-theme="light"] .navbar {
            background: rgba(255, 255, 255, 0.88);
            border-bottom-color: var(--border-color);
        }
        
        [data-theme="light"] .navbar.scrolled {
            background: rgba(255, 255, 255, 0.95);
            box-shadow: var(--shadow-md);
        }
        
        [data-theme="light"] .product-card {
            background: var(--bg-card);
            border-color: var(--border-color);
        }
        
        [data-theme="light"] .product-card:hover {
            background: var(--bg-card-hover);
            border-color: var(--border-accent);
        }
        
        [data-theme="light"] .reco-widget {
            background: var(--bg-card-strong);
            border-color: var(--border-accent);
        }
        
        [data-theme="light"] .filter-bar {
            background: var(--bg-glass);
            border-color: var(--border-color);
        }
        
        [data-theme="light"] .form-input,
        [data-theme="light"] .form-select,
        [data-theme="light"] .form-textarea {
            background: var(--bg-card-strong);
            border-color: var(--border-color);
            color: var(--text-main);
        }
        
        [data-theme="light"] .form-input:focus,
        [data-theme="light"] .form-select:focus,
        [data-theme="light"] .form-textarea:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 4px var(--primary-glow);
        }
        
        [data-theme="light"] .btn-secondary {
            background: var(--bg-glass);
            border-color: var(--border-color);
            color: var(--text-main);
        }
        
        [data-theme="light"] .btn-secondary:hover {
            background: var(--bg-glass-strong);
            border-color: var(--border-accent);
        }
        
        [data-theme="light"] .chat-bubble .bubble-text {
            background: var(--bg-card);
            border-color: var(--border-color);
        }
        
        [data-theme="light"] .user-bubble .bubble-text {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        }
        
        [data-theme="light"] .tag-pill {
            background: var(--bg-glass);
            border-color: var(--border-subtle);
            color: var(--text-muted);
        }
        
        [data-theme="light"] .data-table {
            background: var(--bg-card);
            border-color: var(--border-color);
        }
        
        [data-theme="light"] .data-table th {
            background: var(--bg-glass-strong);
            color: var(--text-dim);
        }
        
        [data-theme="light"] .data-table tbody tr:hover {
            background: var(--bg-glass);
        }
        
        [data-theme="light"] footer {
            background: rgba(255, 255, 255, 0.95);
            border-top-color: var(--border-color);
        }
        
        [data-theme="light"] #aiChatWindow {
            background: var(--bg-card-strong);
            border-color: var(--border-accent);
        }
        
        [data-theme="light"] .chat-header {
            background: var(--bg-glass-strong);
            border-bottom-color: var(--border-color);
        }
        
        [data-theme="light"] .chat-suggestions-bar {
            background: var(--bg-glass);
            border-bottom-color: var(--border-color);
        }
        
        [data-theme="light"] .chat-input-form {
            background: var(--bg-glass-strong);
            border-top-color: var(--border-color);
        }
        
        [data-theme="light"] .chat-input-form input {
            background: var(--bg-card);
            border-color: var(--border-color);
            color: var(--text-main);
        }
        
        [data-theme="light"] .chip-btn {
            background: var(--bg-card);
            border-color: var(--border-color);
            color: var(--text-muted);
        }
        
        [data-theme="light"] .chip-btn:hover {
            background: linear-gradient(135deg, var(--primary), var(--accent));
            color: #fff;
        }
        
        [data-theme="light"] .theme-toggle {
            background: var(--bg-glass);
            border-color: var(--border-color);
            color: var(--text-muted);
        }
        
        [data-theme="light"] .theme-toggle:hover {
            background: var(--bg-glass-strong);
            border-color: var(--border-accent);
            color: var(--text-bright);
        }
        
        [data-theme="light"] .global-loading {
            background: var(--bg-deep);
        }
        
        [data-theme="light"] .toast {
            background: var(--bg-card-strong);
            border-color: var(--border-color);
        }
        
        @media (prefers-contrast: high) {
            [data-theme="light"] {
                --border-color: rgba(15, 23, 42, 0.3);
                --text-muted: #334155;
            }
        }
    `;
    document.head.appendChild(style);

    window.ThemeManager = {
        getTheme: () => currentTheme,
        setTheme: applyTheme,
        toggle: toggleTheme,
        DARK,
        LIGHT
    };
})();