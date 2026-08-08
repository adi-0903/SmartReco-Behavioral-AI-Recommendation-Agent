document.addEventListener('DOMContentLoaded', function() {
    const toggleBtn = document.getElementById('aiChatToggleBtn');
    const closeBtn = document.getElementById('aiChatCloseBtn');
    const chatWindow = document.getElementById('aiChatWindow');
    const chatForm = document.getElementById('aiChatInputForm');
    const chatInput = document.getElementById('aiChatInputText');
    const chatLog = document.getElementById('aiChatMessagesLog');
    const chipBtns = document.querySelectorAll('.chip-btn');

    if (!toggleBtn || !chatWindow) return;

    // Toggle Chat Window
    toggleBtn.addEventListener('click', function() {
        chatWindow.classList.toggle('chat-window-hidden');
        if (!chatWindow.classList.contains('chat-window-hidden')) {
            chatInput.focus();
        }
    });

    closeBtn.addEventListener('click', function() {
        chatWindow.classList.add('chat-window-hidden');
        chatWindow.classList.remove('chat-window-expanded');
    });

    const expandBtn = document.getElementById('aiChatExpandBtn');
    if (expandBtn) {
        expandBtn.addEventListener('click', function() {
            chatWindow.classList.toggle('chat-window-expanded');
            if (chatWindow.classList.contains('chat-window-expanded')) {
                expandBtn.innerHTML = '⤓';
                expandBtn.title = "Exit Fullscreen Mode";
            } else {
                expandBtn.innerHTML = '⤢';
                expandBtn.title = "Toggle Fullscreen Mode";
            }
        });
    }

    // Chip Suggestions
    chipBtns.forEach(function(chip) {
        chip.addEventListener('click', function() {
            const query = this.getAttribute('data-query');
            if (query) {
                chatInput.value = query;
                sendMessage(query);
            }
        });
    });

    // Submit Form
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (text) {
            sendMessage(text);
        }
    });

    function sendMessage(userMessage) {
        // 1. Append User Bubble
        appendBubble('user', userMessage);
        chatInput.value = '';

        // 2. Append Typing Indicator
        const typingId = 'typing_' + Date.now();
        appendTypingIndicator(typingId);

        // 3. Send API Request
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: userMessage })
        })
        .then(function(res) { return res.json(); })
        .then(function(data) {
            removeTypingIndicator(typingId);
            if (data && data.reply) {
                appendBubble('bot', data.reply);
            } else {
                appendBubble('bot', "I couldn't process that query. Ask me any coding, course, or technical problem-solving question!");
            }
        })
        .catch(function(err) {
            removeTypingIndicator(typingId);
            appendBubble('bot', "🤖 I am ready to help with coding, course recommendations, and technical issue solving!");
        });
    }

    function appendBubble(sender, text) {
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble ' + (sender === 'user' ? 'user-bubble' : 'bot-bubble');
        bubble.style.animation = 'bubbleIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)';

        const formattedContent = formatMarkdown(text);

        if (sender === 'bot') {
            bubble.innerHTML = '<span class="bot-icon">🤖</span><div class="bubble-text">' + formattedContent + '</div>';
        } else {
            bubble.innerHTML = '<div class="bubble-text">' + formattedContent + '</div>';
        }

        chatLog.appendChild(bubble);
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    function appendTypingIndicator(id) {
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble bot-bubble';
        bubble.id = id;
        bubble.innerHTML = '<span class="bot-icon">🤖</span><div class="bubble-text" style="color: var(--text-muted); font-style: italic;">Thinking...</div>';
        chatLog.appendChild(bubble);
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    function removeTypingIndicator(id) {
        const elem = document.getElementById(id);
        if (elem) elem.remove();
    }

    function formatMarkdown(text) {
        if (!text) return '';
        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Code blocks ```code```
        html = html.replace(/```([\s\S]*?)```/g, function(match, p1) {
            return '<pre style="background: #0f172a; padding: 0.8rem; border-radius: 6px; border: 1px solid #334155; font-family: monospace; font-size: 0.8rem; overflow-x: auto; margin: 0.5rem 0; color: #38bdf8;"><code>' + p1.trim() + '</code></pre>';
        });

        // Inline code `code`
        html = html.replace(/`([^`]+)`/g, '<code style="background: rgba(255,255,255,0.1); padding: 0.1rem 0.4rem; border-radius: 4px; font-family: monospace; font-size: 0.82rem; color: #38bdf8;">$1</code>');

        // Bold **text**
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Newlines to <br>
        html = html.replace(/\n/g, '<br>');

        return html;
    }
});
