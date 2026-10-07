// app/static/js/chat.js
document.addEventListener("DOMContentLoaded", () => {
    const prechatContainer = document.getElementById('prechat-container');
    const chatContainer = document.getElementById('chat-container');
    const socket = io();

    // --- PRE-CHAT LOGIC ---
    async function initializePreChat() {
        try {
            const response = await fetch('/api/public/prechat_form');
            if (!response.ok) throw new Error('Network response was not ok');
            const config = await response.json();

            if (config.enabled && config.questions && config.questions.length > 0) {
                renderPreChatForm(config.questions, config);
                if(chatContainer) chatContainer.classList.add('hidden');
                if(prechatContainer) {
                    prechatContainer.classList.remove('hidden');
                    prechatContainer.classList.add('flex');
                }
            } else {
                startChat();
            }
        } catch (error) {
            console.error("Could not fetch pre-chat config, starting chat directly:", error);
            startChat();
        }
    }

    function renderPreChatForm(questions, config) {
        if (!prechatContainer) return;

        const form = document.createElement('form');
        form.id = 'prechat-form-dynamic';
        form.className = 'space-y-6 w-full max-w-lg mx-auto';

        const title = document.createElement('h2');
        title.textContent = 'Sohbete Başlamadan Önce';
        title.className = 'text-2xl font-bold text-center text-gray-800';
        form.appendChild(title);

        questions.forEach(q => {
            const fieldContainer = document.createElement('div');
            const label = document.createElement('label');
            label.textContent = q.text + (q.required ? ' *' : '');
            label.className = 'block text-sm font-medium text-gray-700';
            label.htmlFor = `prechat-field-${q.id}`;
            fieldContainer.appendChild(label);

            let input;
            switch (q.type) {
                case 'textarea':
                    input = document.createElement('textarea');
                    input.className = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500';
                    break;
                case 'multiple-choice':
                    input = document.createElement('select');
                    input.className = 'mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md';
                    // Add a default, disabled option
                    const defaultOption = document.createElement('option');
                    defaultOption.textContent = 'Lütfen birini seçin...';
                    defaultOption.value = '';
                    defaultOption.disabled = true;
                    defaultOption.selected = true;
                    input.appendChild(defaultOption);

                    (q.options || []).forEach(opt => {
                        const option = document.createElement('option');
                        option.value = opt;
                        option.textContent = opt;
                        input.appendChild(option);
                    });
                    break;
                default: // 'text', 'email'
                    input = document.createElement('input');
                    input.type = q.type === 'email' ? 'email' : 'text';
                    input.className = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500';
            }

            input.id = `prechat-field-${q.id}`;
            input.name = q.id;
            if (q.required) {
                input.required = true;
            }
            fieldContainer.appendChild(input);
            form.appendChild(fieldContainer);
        });

        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.textContent = 'Sohbeti Başlat';
        submitButton.className = 'w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500';
        form.appendChild(submitButton);

        prechatContainer.innerHTML = ''; // Clear previous content
        prechatContainer.appendChild(form);

        form.addEventListener('submit', (e) => handlePreChatSubmit(e, config));
    }

    async function handlePreChatSubmit(event, config) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        const submissionWithIds = {};
        let allValid = true;

        // Basic validation
        for (const [key, value] of formData.entries()) {
            const field = form.querySelector(`[name="${key}"]`);
            if (field.required && !value) {
                allValid = false;
                // You could add some error indication here
                field.style.borderColor = 'red';
            } else {
                 field.style.borderColor = '';
            }
            submissionWithIds[key] = value;
        }

        if (!allValid) {
            alert('Lütfen tüm zorunlu alanları doldurun.');
            return;
        }
        const finalPayload = {};
        const questionMap = new Map(config.questions.map(q => [q.id, q.text]));
        for (const [id, value] of Object.entries(submissionWithIds)) {
            const questionText = questionMap.get(id);
            if (questionText) {
                finalPayload[questionText] = value;
            }
        }
        // Find the 'name' and 'email' questions with a highly flexible search
        const nameQuestion = (config.questions || []).find(q =>
            (q.id && q.id.toLowerCase() === 'name') ||
            (q.type && q.type.toLowerCase() === 'name') ||
            (q.text && (q.text.toLowerCase().includes('ad') || q.text.toLowerCase().includes('isim')))
        );
        const emailQuestion = (config.questions || []).find(q =>
            (q.id && q.id.toLowerCase() === 'email') ||
            (q.type && q.type.toLowerCase() === 'email') ||
            (q.text && q.text.toLowerCase().includes('mail'))
        );

        let userName = `user_${new Date().getTime()}`; // Fallback name
        let userEmail = null;

        if (nameQuestion && submissionWithIds[nameQuestion.id]) {
            userName = submissionWithIds[nameQuestion.id];
        }
        if (emailQuestion && submissionWithIds[emailQuestion.id]) {
            userEmail = submissionWithIds[emailQuestion.id];
        }
        finalPayload.user_id = userName; // Keep user_id for logging consistency


        try {
            const response = await fetch('/api/prechat/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(finalPayload)
            });

            if (!response.ok) {
                throw new Error('Pre-chat submission failed');
            }

            // Notify the server to update the user details for this session
            socket.emit('update_user_details', { name: userName, email: userEmail });

            if(prechatContainer) {
                prechatContainer.classList.add('hidden');
                prechatContainer.classList.remove('flex');
            }
            if(chatContainer) chatContainer.classList.remove('hidden');
            startChat();

        } catch (error) {
            console.error("Error submitting pre-chat form:", error);
            const errorP = document.createElement('p');
            errorP.textContent = 'Form gönderilirken bir hata oluştu. Lütfen tekrar deneyin.';
            errorP.className = 'text-red-500 text-sm mt-2 text-center';
            form.appendChild(errorP);
        }
    }
    // --- END PRE-CHAT LOGIC ---

    function startChat() {
         if (!chatContainer) return; // Don't run chat logic if container is not on the page
         chatContainer.style.opacity = '1'; // Make it visible if it was hidden

        const applyTheme = (themeSettings) => {
            if (!themeSettings) return;

            const styleId = 'dynamic-theme-styles';
        let styleElement = document.getElementById(styleId);
        if (!styleElement) {
            styleElement = document.createElement('style');
            styleElement.id = styleId;
            document.head.appendChild(styleElement);
        }

        let fontFaceCss = '';
        if (themeSettings.custom_font_path && themeSettings.custom_font_family) {
            fontFaceCss = `
            @font-face {
                font-family: "${themeSettings.custom_font_family}";
                src: url('/static/${themeSettings.custom_font_path}');
            }
            `;
        }

        const chatFontFamily = themeSettings.font === 'CustomFont' && themeSettings.custom_font_family
            ? `"${themeSettings.custom_font_family}", sans-serif`
            : `"${themeSettings.font || 'Inter'}", sans-serif`;

        const css = `
            ${fontFaceCss}
            :root {
                /* Global */
                --chat-font-family: ${chatFontFamily};
                --chat-font-size: ${themeSettings.font_size ? (themeSettings.font_size.includes('px') ? themeSettings.font_size : `${themeSettings.font_size}px`) : '14px'};
                --header-bg: ${themeSettings.primary_color || '#4F46E5'};

                /* Light Mode Defaults */
                --page-bg-color: ${themeSettings.page_bg_color_light || '#F3F4F6'};
                --chat-bg-color: ${themeSettings.chat_bg_color_light || '#FFFFFF'};
                --input-bg-color: ${themeSettings.input_bg_color_light || '#FFFFFF'};
                --input-text-color: ${themeSettings.input_text_color_light || '#1F2937'};
                --bot-bubble-bg: ${themeSettings.bot_bubble_color_light || '#E5E7EB'};
                --bot-bubble-text: ${themeSettings.bot_text_color_light || '#1F2937'};
                --user-bubble-bg: ${themeSettings.user_bubble_color_light || '#4F46E5'};
                --user-bubble-text: ${themeSettings.user_text_color_light || '#FFFFFF'};
            }

            html.dark {
                /* Dark Mode Overrides */
                --page-bg-color: ${themeSettings.page_bg_color_dark || '#111827'};
                --chat-bg-color: ${themeSettings.chat_bg_color_dark || '#1F2937'};
                --input-bg-color: ${themeSettings.input_bg_color_dark || '#374151'};
                --input-text-color: ${themeSettings.input_text_color_dark || '#F9FAFB'};
                --bot-bubble-bg: ${themeSettings.bot_bubble_color_dark || '#374151'};
                --bot-bubble-text: ${themeSettings.bot_text_color_dark || '#F9FAFB'};
                --user-bubble-bg: ${themeSettings.user_bubble_color_dark || '#4F46E5'};
                --user-bubble-text: ${themeSettings.user_text_color_dark || '#FFFFFF'};
            }

            body {
                font-family: var(--chat-font-family);
                background-color: var(--page-bg-color);
            }

            #chatbox {
                background-color: var(--chat-bg-color);
                font-size: var(--chat-font-size);
            }

            #userInput {
                background-color: var(--input-bg-color);
                color: var(--input-text-color);
            }

            .bot-bubble {
                background-color: var(--bot-bubble-bg);
                color: var(--bot-bubble-text);
            }

            .user-bubble {
                background-color: var(--user-bubble-bg);
                color: var(--user-bubble-text);
            }

            #chat-header {
                background-color: var(--header-bg);
            }
        `;
        styleElement.innerHTML = css;

        const botIcon = document.getElementById('chat-header-bot-icon');
        if (botIcon && themeSettings.bot_icon_path) {
            botIcon.src = `/static/${themeSettings.bot_icon_path}`;
        }
    };

    fetch('/api/public/theme')
        .then(response => response.json())
        .then(themeSettings => {
            applyTheme(themeSettings);
        })
        .catch(error => {
            console.error('Error fetching theme settings:', error);
        });

    // --- TEMA DEĞİŞTİRME MEKANİZMASI ---
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    if (themeToggleBtn) {
        const lightIcon = themeToggleBtn.querySelector('.theme-icon-light');
        const darkIcon = themeToggleBtn.querySelector('.theme-icon-dark');

        const setToggleState = (isDark) => {
            if (isDark) {
                document.documentElement.classList.add('dark');
                if(lightIcon) lightIcon.classList.add('hidden');
                if(darkIcon) darkIcon.classList.remove('hidden');
            } else {
                document.documentElement.classList.remove('dark');
                if(lightIcon) lightIcon.classList.remove('hidden');
                if(darkIcon) darkIcon.classList.add('hidden');
            }
        };

        themeToggleBtn.addEventListener('click', () => {
            const isDark = document.documentElement.classList.toggle('dark');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            setToggleState(isDark);
        });

        // Sayfa yüklendiğinde temayı uygula
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            setToggleState(savedTheme === 'dark');
        } else {
            const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
            setToggleState(prefersDark);
        }
    }
    // --- Bitiş ---

    const chatbox = document.getElementById('chatbox');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    let bubblesContainer = null; // Baloncukları tutacak global referans
    let inactivityTimer = null; // Hareketsizlik zamanlayıcısı
    let userChatDisplayId = null; // Kullanıcı dostu sohbet ID'sini saklamak için


    const style = document.createElement('style');
    style.textContent = `
        /* YAZIYOR... (TYPING) ANIMASYONU */
        .typing-dot-container span {
            height: 8px;
            width: 8px;
            background-color: #9ca3af;
            border-radius: 50%;
            display: inline-block;
            animation: typing-blink 1.4s infinite both;
        }
        .typing-dot-container span:nth-child(2) {
            animation-delay: 0.2s;
        }
        .typing-dot-container span:nth-child(3) {
            animation-delay: 0.4s;
        }
        @keyframes typing-blink {
            0% { opacity: 0.2; }
            20% { opacity: 1; }
            100% { opacity: 0.2; }
        }

        /* MESAJ GELIS ANIMASYONU */
        .message-bubble-animate {
            animation: fade-in-slide-up 0.5s ease-out forwards;
        }
        @keyframes fade-in-slide-up {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* Diger Stiller */
        .bubble-btn {
            background-color: #A5B4FC;
            color: #3730A3;
            border: 1px solid #6366F1;
            padding: 8px 16px;
            border-radius: 16px;
            margin: 4px;
            cursor: pointer;
            transition: background-color 0.3s, color 0.3s;
        }
        .bubble-btn:hover {
            background-color: #818CF8;
            color: white;
        }
        .bubbles-wrapper {
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-start;
            margin-top: 8px;
        }
    `;
    document.head.appendChild(style);

    const addMessage = (text, sender, animate = false) => {
        const messageWrapper = document.createElement('div');
        const messageBubble = document.createElement('div');

        messageWrapper.classList.add('flex', 'mb-4');
        if (animate) {
            messageWrapper.classList.add('message-bubble-animate');
        }

        messageBubble.classList.add('p-3', 'rounded-lg', 'max-w-md', 'shadow');
        messageBubble.textContent = text;

        if (sender === 'user') {
            messageWrapper.classList.add('justify-end');
            messageBubble.classList.add('user-bubble');
        } else if (sender === 'system') {
            messageWrapper.classList.add('justify-center');
            messageBubble.classList.add('bg-yellow-200', 'text-yellow-800', 'text-sm');
        } else { // bot or admin
            messageWrapper.classList.add('justify-start');
            messageBubble.classList.add('bot-bubble');
        }

        messageWrapper.appendChild(messageBubble);
        chatbox.appendChild(messageWrapper);
        chatbox.scrollTop = chatbox.scrollHeight;
        return messageWrapper;
    };

    const closeChat = (message) => {
        addMessage(message, "system");
        toggleUserInput(false);
        removeBubbles();
        if (socket.connected) {
            socket.close();
        }
        clearTimeout(inactivityTimer);
    };

    const resetInactivityTimer = () => {
        clearTimeout(inactivityTimer);
        inactivityTimer = setTimeout(() => {
            closeChat("5 dakikadır işlem yapmadığınız için oturum sonlandırıldı.");
        }, 300000); // 5 dakika
    };

    const addTypingIndicator = () => {
        const messageWrapper = document.createElement('div');
        messageWrapper.id = 'typing-indicator';
        const messageBubble = document.createElement('div');
        messageWrapper.classList.add('flex', 'mb-4', 'justify-start');
        messageBubble.classList.add('p-3', 'rounded-lg', 'max-w-md', 'shadow', 'bg-gray-200');
        const typingContainer = document.createElement('div');
        typingContainer.classList.add('typing-dot-container', 'space-x-1.5');
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('span');
            typingContainer.appendChild(dot);
        }
        messageBubble.appendChild(typingContainer);
        messageWrapper.appendChild(messageBubble);
        chatbox.appendChild(messageWrapper);
        chatbox.scrollTop = chatbox.scrollHeight;
        return messageWrapper;
    };

    const removeTypingIndicator = () => {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    };

    const addBubbles = (bubbles) => {
        if (bubblesContainer) {
            bubblesContainer.remove();
        }
        bubblesContainer = document.createElement('div');
        bubblesContainer.classList.add('bubbles-wrapper');
        
        bubbles.forEach(bubble => {
            const bubbleBtn = document.createElement('button');
            bubbleBtn.classList.add('bubble-btn');
            bubbleBtn.textContent = bubble.text;
            bubbleBtn.dataset.value = bubble.value;
            bubbleBtn.addEventListener('click', () => handleBubbleClick(bubble.value, bubble.text));
            bubblesContainer.appendChild(bubbleBtn);
        });

        chatbox.appendChild(bubblesContainer);
        chatbox.scrollTop = chatbox.scrollHeight;
    };

    const removeBubbles = () => {
        if (bubblesContainer) {
            bubblesContainer.remove();
            bubblesContainer = null;
        }
    };

    const toggleUserInput = (enabled) => {
        userInput.disabled = !enabled;
        sendBtn.disabled = !enabled;
        if (enabled) {
            userInput.focus();
        }
    };

    const sendMessage = (data) => {
        toggleUserInput(false);
        removeBubbles();
        addTypingIndicator();
        socket.emit('user_message', data);
    };

    const showSurvey = (surveyData) => {
        // Prevent showing multiple surveys
        if (document.getElementById('survey-container')) return;

        toggleUserInput(false);
        removeBubbles();
        clearTimeout(inactivityTimer); // Stop inactivity timer when survey is shown

        const surveyContainer = document.createElement('div');
        surveyContainer.id = 'survey-container';
        surveyContainer.classList.add('p-4', 'rounded-lg', 'shadow-md', 'my-4', 'border');
        surveyContainer.style.backgroundColor = surveyData.theme.background_color || '#FFFFFF';
        surveyContainer.style.color = surveyData.theme.text_color || '#000000';
        surveyContainer.style.borderColor = surveyData.theme.bubble_color || '#E5E7EB';


        const surveyForm = document.createElement('form');
        surveyForm.id = 'survey-form';

        surveyData.questions.forEach(q => {
            const questionWrapper = document.createElement('div');
            questionWrapper.classList.add('mb-4');

            const questionLabel = document.createElement('label');
            questionLabel.classList.add('block', 'mb-2', 'font-medium');
            questionLabel.textContent = q.text;
            questionLabel.htmlFor = q.id;
            questionWrapper.appendChild(questionLabel);

            if (q.type === 'rating') {
                const ratingContainer = document.createElement('div');
                ratingContainer.classList.add('flex', 'space-x-2');
                q.options.forEach(opt => {
                    const ratingBtn = document.createElement('button');
                    ratingBtn.type = 'button';
                    ratingBtn.textContent = opt;
                    ratingBtn.dataset.value = opt;
                    ratingBtn.classList.add('p-2', 'border', 'rounded-full', 'w-10', 'h-10', 'flex', 'items-center', 'justify-center', 'transition-colors');
                    ratingBtn.style.backgroundColor = surveyData.theme.bubble_color || '#F0F0F0';
                    ratingBtn.style.color = surveyData.theme.text_color || '#000000';
                    ratingBtn.style.borderColor = surveyData.theme.button_color || '#4F46E5';


                    ratingBtn.addEventListener('click', () => {
                        // Remove selected style from siblings
                        ratingContainer.querySelectorAll('button').forEach(btn => {
                            btn.classList.remove('selected-rating');
                            btn.style.backgroundColor = surveyData.theme.bubble_color || '#F0F0F0';
                            btn.style.color = surveyData.theme.text_color || '#000000';
                        });
                        // Add selected style to clicked button
                        ratingBtn.classList.add('selected-rating');
                        ratingBtn.style.backgroundColor = surveyData.theme.button_color || '#4F46E5';
                        ratingBtn.style.color = surveyData.theme.button_text_color || '#FFFFFF';

                        // Store value in a hidden input for submission
                        let hiddenInput = questionWrapper.querySelector(`input[name="${q.id}"]`);
                        if (!hiddenInput) {
                            hiddenInput = document.createElement('input');
                            hiddenInput.type = 'hidden';
                            hiddenInput.name = q.id;
                            questionWrapper.appendChild(hiddenInput);
                        }
                        hiddenInput.value = opt;
                    });
                    ratingContainer.appendChild(ratingBtn);
                });
                questionWrapper.appendChild(ratingContainer);

            } else if (q.type === 'multiple-choice') {
                const choiceContainer = document.createElement('div');
                choiceContainer.classList.add('flex', 'flex-wrap', 'gap-2');
                q.options.forEach(opt => {
                    const choiceBtn = document.createElement('button');
                    choiceBtn.type = 'button';
                    choiceBtn.textContent = opt;
                    choiceBtn.dataset.value = opt;
                    choiceBtn.classList.add('p-2', 'border', 'rounded-md', 'transition-colors');
                    choiceBtn.style.backgroundColor = surveyData.theme.bubble_color || '#F0F0F0';
                    choiceBtn.style.color = surveyData.theme.text_color || '#000000';
                    choiceBtn.style.borderColor = surveyData.theme.button_color || '#4F46E5';

                    choiceBtn.addEventListener('click', () => {
                        choiceContainer.querySelectorAll('button').forEach(btn => {
                            btn.classList.remove('selected-choice');
                            btn.style.backgroundColor = surveyData.theme.bubble_color || '#F0F0F0';
                            btn.style.color = surveyData.theme.text_color || '#000000';
                        });
                        choiceBtn.classList.add('selected-choice');
                        choiceBtn.style.backgroundColor = surveyData.theme.button_color || '#4F46E5';
                        choiceBtn.style.color = surveyData.theme.button_text_color || '#FFFFFF';

                        let hiddenInput = questionWrapper.querySelector(`input[name="${q.id}"]`);
                        if (!hiddenInput) {
                            hiddenInput = document.createElement('input');
                            hiddenInput.type = 'hidden';
                            hiddenInput.name = q.id;
                            questionWrapper.appendChild(hiddenInput);
                        }
                        hiddenInput.value = opt;
                    });
                    choiceContainer.appendChild(choiceBtn);
                });
                questionWrapper.appendChild(choiceContainer);
            } else if (q.type === 'textarea') {
                const textarea = document.createElement('textarea');
                textarea.id = q.id;
                textarea.name = q.id;
                textarea.rows = 3;
                textarea.classList.add('w-full', 'p-2', 'border', 'rounded-md');
                textarea.style.backgroundColor = surveyData.theme.bubble_color || '#F0F0F0';
                textarea.style.color = surveyData.theme.text_color || '#000000';
                textarea.style.borderColor = surveyData.theme.button_color || '#4F46E5';

                questionWrapper.appendChild(textarea);
            }
            surveyForm.appendChild(questionWrapper);
        });

        const submitBtn = document.createElement('button');
        submitBtn.type = 'submit';
        submitBtn.textContent = 'Gönder';
        submitBtn.classList.add('w-full', 'p-2', 'rounded-md', 'font-semibold', 'transition-colors');
        submitBtn.style.backgroundColor = surveyData.theme.button_color || '#4F46E5';
        submitBtn.style.color = surveyData.theme.button_text_color || '#FFFFFF';


        surveyForm.appendChild(submitBtn);
        surveyContainer.appendChild(surveyForm);
        chatbox.appendChild(surveyContainer);
        chatbox.scrollTop = chatbox.scrollHeight;

        surveyForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(surveyForm);
            const surveyResult = {
                chat_session_id: socket.id, // This is the socket.id
                chat_display_id: userChatDisplayId || null // This is the one for display
            };
            for (const [key, value] of formData.entries()) {
                surveyResult[key] = value;
            }

            fetch('/api/survey/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(surveyResult),
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    surveyContainer.innerHTML = `<p class="text-center">${data.message}</p>`;
                } else {
                    surveyContainer.innerHTML = `<p class="text-center text-red-500">Anket gönderilemedi. Lütfen daha sonra tekrar deneyin.</p>`;
                }
            })
            .catch(error => {
                console.error('Survey submission error:', error);
                surveyContainer.innerHTML = `<p class="text-center text-red-500">Bir hata oluştu. Lütfen daha sonra tekrar deneyin.</p>`;
            });
        });
    };

    const handleSend = () => {
        const userText = userInput.value.trim();
        if (!userText) return;
        addMessage(userText, 'user', true);
        userInput.value = '';
        sendMessage({ msg: userText });
        resetInactivityTimer();
    };

    const handleBubbleClick = (value, text) => {
        addMessage(text, 'user', true);
        sendMessage({ value: value });
        resetInactivityTimer();
    };

    // Sunucudan gelen yeni mesajları dinle
    socket.on('new_message', (data) => {
        removeTypingIndicator();

        const sender = data.sender || 'bot';
        const messageText = data.response || data.text || "Üzgünüm, bir hata oluştu.";

        addMessage(messageText, sender, true);

        if (sender === 'bot') {
            if (data.bubbles && data.bubbles.length > 0) {
                addBubbles(data.bubbles);
                toggleUserInput(false);
            } else {
                toggleUserInput(true);
            }
        } else { // admin or system
            removeBubbles();
            toggleUserInput(true);
        }
    });

    socket.on('connect', () => {
        console.log('Sunucuya başarıyla bağlandı. SID:', socket.id);
        resetInactivityTimer();
    });

    socket.on('disconnect', () => {
        console.log('Sunucuyla bağlantı kesildi.');
        closeChat("Bağlantı kesildi. Lütfen sayfayı yenileyin.");
    });

    socket.on('show_survey', (surveyData) => {
        if (surveyData && surveyData.enabled) {
            showSurvey(surveyData);
        }
    });

    socket.on('session_details', (data) => {
        if (data.chat_display_id) {
            userChatDisplayId = data.chat_display_id;
        }
    });

    const requestHumanBtn = document.getElementById('requestHumanBtn');

    const handleRequestHuman = () => {
        // The server will now send the "requesting..." message, so we just send the event.
        sendMessage({ request: 'human_agent' });
        // Butonu geçici olarak devre dışı bırak
        requestHumanBtn.disabled = true;
        requestHumanBtn.textContent = "İstek Gönderildi";
        setTimeout(() => {
            requestHumanBtn.disabled = false;
            requestHumanBtn.textContent = "Müşteri Temsilcisine Bağlan";
        }, 10000); // 10 saniye sonra tekrar aktif et
    };

    sendBtn.addEventListener('click', handleSend);
    userInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleSend(); });
    requestHumanBtn.addEventListener('click', handleRequestHuman);

    socket.emit('start_chat');
    toggleUserInput(true);
    }

    initializePreChat();
});
