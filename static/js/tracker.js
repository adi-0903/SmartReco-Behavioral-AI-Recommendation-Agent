/**
 * SmartReco Non-Blocking Client-Side Event Tracker
 * Collects page views, product interactions, search queries, dwell time, and recommendation clicks.
 * Uses event queue batching and navigator.sendBeacon for optimal performance.
 */
(function() {
    const BATCH_INTERVAL_MS = 3000;
    const MAX_BATCH_SIZE = 5;
    const ENDPOINT = '/api/events/batch';

    let eventQueue = [];
    let sessionId = localStorage.getItem('smartreco_session_id');
    if (!sessionId) {
        sessionId = 'sess_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now();
        localStorage.setItem('smartreco_session_id', sessionId);
    }

    let pageStartTime = Date.now();
    let currentProductInfo = null;

    // SmartReco Tracker API object
    window.SmartRecoTracker = {
        getSessionId: function() {
            return sessionId;
        },

        pushEvent: function(eventType, targetId, details = {}, durationMs = 0) {
            const payload = {
                session_id: sessionId,
                event_type: eventType,
                target_id: targetId ? String(targetId) : null,
                details: details,
                duration_ms: Math.round(durationMs),
                timestamp: new Date().toISOString()
            };
            eventQueue.push(payload);

            if (eventQueue.length >= MAX_BATCH_SIZE) {
                this.flush();
            }
        },

        trackPageView: function(pagePath, pageTitle) {
            this.pushEvent('page_view', pagePath, { path: pagePath, title: pageTitle });
        },

        trackSearch: function(query, resultsCount) {
            if (!query || query.trim() === '') return;
            this.pushEvent('search', query.trim(), { query: query.trim(), results_count: resultsCount });
        },

        trackProductView: function(productId, title, category) {
            currentProductInfo = { id: productId, title: title, category: category };
            pageStartTime = Date.now();
            this.pushEvent('product_view', productId, {
                product_id: productId,
                product_title: title,
                category: category
            });
        },

        trackCategoryFilter: function(category) {
            this.pushEvent('category_filter', category, { category: category });
        },

        trackClickRecommendation: function(recId, productId) {
            this.pushEvent('click_recommendation', productId, { recommendation_id: recId, product_id: productId });
        },

        flush: function() {
            if (eventQueue.length === 0) return;
            
            const batchToSend = [...eventQueue];
            eventQueue = [];

            const dataStr = JSON.stringify({ events: batchToSend });

            if (navigator.sendBeacon) {
                const blob = new Blob([dataStr], { type: 'application/json' });
                navigator.sendBeacon(ENDPOINT, blob);
            } else {
                fetch(ENDPOINT, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: dataStr,
                    keepalive: true
                }).catch(err => console.error("SmartReco tracking flush error:", err));
            }
        }
    };

    // Periodic flush timer
    setInterval(() => {
        SmartRecoTracker.flush();
    }, BATCH_INTERVAL_MS);

    // Flush on page exit / tab switch & record dwell time
    window.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
            const dwellDuration = Date.now() - pageStartTime;
            if (currentProductInfo && dwellDuration > 1000) {
                SmartRecoTracker.pushEvent('dwell_time', currentProductInfo.id, {
                    product_id: currentProductInfo.id,
                    product_title: currentProductInfo.title,
                    category: currentProductInfo.category
                }, dwellDuration);
            }
            SmartRecoTracker.flush();
        }
    });

    window.addEventListener('beforeunload', function() {
        const dwellDuration = Date.now() - pageStartTime;
        if (currentProductInfo && dwellDuration > 1000) {
            SmartRecoTracker.pushEvent('dwell_time', currentProductInfo.id, {
                product_id: currentProductInfo.id,
                product_title: currentProductInfo.title,
                category: currentProductInfo.category
            }, dwellDuration);
        }
        SmartRecoTracker.flush();
    });

    // Auto-track initial page view on load
    document.addEventListener('DOMContentLoaded', function() {
        SmartRecoTracker.trackPageView(window.location.pathname, document.title);
    });
})();
