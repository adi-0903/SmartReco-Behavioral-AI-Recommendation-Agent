/**
 * SmartReco UI Enhancements
 * Loading states, error handling, accessibility improvements
 */

(function() {
    'use strict';

    // Global loading state manager
    window.SmartRecoUI = {
        showLoading: function(message) {
            const overlay = document.getElementById('global-loading');
            if (overlay) {
                const msg = overlay.querySelector('p');
                if (msg && message) msg.textContent = message;
                overlay.classList.remove('hidden');
                overlay.setAttribute('aria-busy', 'true');
            }
        },
        
        hideLoading: function() {
            const overlay = document.getElementById('global-loading');
            if (overlay) {
                overlay.classList.add('hidden');
                overlay.setAttribute('aria-busy', 'false');
            }
        },
        
        showToast: function(message, type = 'info', duration = 5000) {
            const container = document.getElementById('toast-container');
            if (!container) return;
            
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.setAttribute('role', 'alert');
            toast.setAttribute('aria-live', 'polite');
            toast.innerHTML = `
                <span class="toast-icon" aria-hidden="true">${type === 'error' ? '⚠️' : type === 'success' ? '✅' : 'ℹ️'}</span>
                <span class="toast-message">${message}</span>
                <button class="toast-close" aria-label="Dismiss">&times;</button>
            `;
            
            container.appendChild(toast);
            
            // Animate in
            requestAnimationFrame(() => toast.classList.add('show'));
            
            // Auto-dismiss
            const dismiss = () => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            };
            
            toast.querySelector('.toast-close').addEventListener('click', dismiss);
            if (duration > 0) setTimeout(dismiss, duration);
        },
        
        // Form validation helpers
        validateForm: function(form) {
            const inputs = form.querySelectorAll('[required]');
            let isValid = true;
            
            inputs.forEach(input => {
                if (!input.value.trim()) {
                    this.showFieldError(input, 'This field is required');
                    isValid = false;
                } else if (input.type === 'email' && !this.isValidEmail(input.value)) {
                    this.showFieldError(input, 'Please enter a valid email address');
                    isValid = false;
                } else if (input.type === 'password' && input.value.length < 8) {
                    this.showFieldError(input, 'Password must be at least 8 characters');
                    isValid = false;
                } else {
                    this.clearFieldError(input);
                }
            });
            
            return isValid;
        },
        
        isValidEmail: function(email) {
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
        },
        
        showFieldError: function(input, message) {
            this.clearFieldError(input);
            input.classList.add('error');
            input.setAttribute('aria-invalid', 'true');
            input.setAttribute('aria-describedby', input.id + '-error');
            
            const errorEl = document.createElement('div');
            errorEl.id = input.id + '-error';
            errorEl.className = 'field-error';
            errorEl.textContent = message;
            input.parentNode.appendChild(errorEl);
        },
        
        clearFieldError: function(input) {
            input.classList.remove('error');
            input.removeAttribute('aria-invalid');
            input.removeAttribute('aria-describedby');
            const errorEl = document.getElementById(input.id + '-error');
            if (errorEl) errorEl.remove();
        },
        
        // Enhanced fetch with loading state
        fetchWithLoading: async function(url, options = {}) {
            const showLoader = options.showLoader !== false;
            if (showLoader) this.showLoading(options.loadingMessage);
            
            try {
                const response = await fetch(url, options);
                if (!response.ok) {
                    const error = await response.json().catch(() => ({ message: 'Request failed' }));
                    throw new Error(error.message || `HTTP ${response.status}`);
                }
                return await response.json();
            } finally {
                if (showLoader) this.hideLoading();
            }
        },
        
        // Accessibility: Focus management
        trapFocus: function(element) {
            const focusableElements = element.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];
            
            element.addEventListener('keydown', function(e) {
                if (e.key === 'Tab') {
                    if (e.shiftKey && document.activeElement === firstElement) {
                        e.preventDefault();
                        lastElement.focus();
                    } else if (!e.shiftKey && document.activeElement === lastElement) {
                        e.preventDefault();
                        firstElement.focus();
                    }
                }
                
                if (e.key === 'Escape') {
                    const closeBtn = element.querySelector('[data-close], .chat-close-btn');
                    if (closeBtn) closeBtn.click();
                }
            });
            
            if (firstElement) firstElement.focus();
        }
    };
    
    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        // Add loading states to all forms
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', function(e) {
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn && !submitBtn.disabled) {
                    submitBtn.disabled = true;
                    submitBtn.dataset.originalText = submitBtn.innerHTML;
                    submitBtn.innerHTML = '<span class="btn-spinner" aria-hidden="true"></span> Processing...';
                    submitBtn.setAttribute('aria-busy', 'true');
                    
                    // Re-enable after 10s as fallback
                    setTimeout(() => {
                        if (submitBtn.disabled) {
                            submitBtn.disabled = false;
                            submitBtn.innerHTML = submitBtn.dataset.originalText;
                            submitBtn.removeAttribute('aria-busy');
                        }
                    }, 10000);
                }
            });
        });
        
        // Add loading states to all links with data-loading attribute
        document.querySelectorAll('a[data-loading]').forEach(link => {
            link.addEventListener('click', function() {
                if (!this.classList.contains('btn')) return;
                this.classList.add('loading');
                this.setAttribute('aria-busy', 'true');
            });
        });
        
        // Enhance chat widget accessibility
        const chatToggle = document.getElementById('aiChatToggleBtn');
        const chatWindow = document.getElementById('aiChatWindow');
        const chatClose = document.getElementById('aiChatCloseBtn');
        const chatInput = document.getElementById('aiChatInputText');
        
        if (chatToggle && chatWindow) {
            chatToggle.addEventListener('click', function() {
                const isExpanded = chatWindow.classList.toggle('chat-window-hidden');
                chatToggle.setAttribute('aria-expanded', !isExpanded);
                
                if (!isExpanded) {
                    // Focus input when opened
                    setTimeout(() => {
                        if (chatInput) chatInput.focus();
                    }, 300);
                    SmartRecoUI.trapFocus(chatWindow);
                }
            });
            
            if (chatClose) {
                chatClose.addEventListener('click', function() {
                    chatWindow.classList.add('chat-window-hidden');
                    chatToggle.setAttribute('aria-expanded', 'false');
                    chatToggle.focus();
                });
            }
        }
        
        // Show/hide typing indicator
        window.showTypingIndicator = function() {
            const indicator = document.getElementById('aiChatTypingIndicator');
            if (indicator) indicator.classList.remove('hidden');
        };
        
        window.hideTypingIndicator = function() {
            const indicator = document.getElementById('aiChatTypingIndicator');
            if (indicator) indicator.classList.add('hidden');
        };
        
        // Keyboard navigation for suggestion chips
        document.querySelectorAll('.chip-btn').forEach(chip => {
            chip.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.click();
                }
            });
        });
        
        // Smooth scroll for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    target.focus({ preventScroll: true });
                }
            });
        });
        
        // Announce dynamic content changes for screen readers
        const announce = (message) => {
            const announcer = document.createElement('div');
            announcer.setAttribute('role', 'status');
            announcer.setAttribute('aria-live', 'polite');
            announcer.className = 'visually-hidden';
            announcer.textContent = message;
            document.body.appendChild(announcer);
            setTimeout(() => announcer.remove(), 1000);
        };
        
        // Expose announce function globally
        window.announceToScreenReader = announce;
    });
    
    // Handle fetch errors globally
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        try {
            const response = await originalFetch.apply(this, args);
            if (!response.ok && response.status >= 500) {
                SmartRecoUI.showToast('Server error. Please try again later.', 'error');
            }
            return response;
        } catch (error) {
            if (!error.message.includes('Failed to fetch')) {
                SmartRecoUI.showToast('Network error. Please check your connection.', 'error');
            }
            throw error;
        }
    };
})();