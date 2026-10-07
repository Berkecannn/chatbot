// app/static/js/admin.js

// İki yönlü çeviri için haritalar
const stateTranslations = {
    "awaiting_order_info": "Sipariş Bilgisi Bekleniyor",
    "awaiting_user_query": "Kullanıcı Sorusu Bekleniyor"
};

// Teknik ID'den Türkçe'ye çevirir
function translateState(technicalId) {
    return stateTranslations[technicalId] || technicalId;
}

// Türkçe'den teknik ID'ye geri çevirir
function untranslateState(turkishText) {
    const found = Object.entries(stateTranslations).find(([key, value]) => value === turkishText);
    return found ? found[0] : turkishText;
}


document.addEventListener('DOMContentLoaded', () => {
    // Helper function to prevent excessive API calls on input
    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), delay);
        };
    }

    const loginView = document.getElementById('login-view');
    const signupView = document.getElementById('signup-view');

    const actionNamesCache = new Map();

    async function loadActionNames() {
        try {
            const actions = await apiRequest('/api/actions');
            actions.forEach(action => {
                actionNamesCache.set(action.id, action.name);
            });
        } catch (error) {
            console.error("Eylem isimleri yüklenemedi:", error);
            // Fallback for critical actions if API fails
            actionNamesCache.set("telegram_order_lookup", "Telegram Sipariş Sorgulama");
        }
    }

    function translate(technicalId) {
        if (!technicalId) return 'Yok';
        // First, try the cache which gets data from the API
        if (actionNamesCache.has(technicalId)) {
            return actionNamesCache.get(technicalId);
        }
        // Fallback for cases where cache might not be populated yet or ID is new
        if (technicalId.startsWith('start_flow:')) {
            const flowName = technicalId.split(':')[1].replace(/_/g, ' ');
            // Capitalize first letter of each word for a cleaner look
            const prettyName = flowName.split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
            return `Akış Başlat: ${prettyName}`;
        }
        return technicalId; // Return the ID itself if no translation is found
    }

    // --- Permission-based Menu Rendering ---
    const userPerms = window.userPermissions;
    if (userPerms && userPerms.role === 'user') {
        const allNavLinkIds = [
            'nav-dashboard', 'nav-users', 'nav-unanswered', 'nav-answered',
            'nav-library', 'nav-notifications', 'nav-chats', 'nav-archives',
            'nav-settings', 'nav-connections'
        ];

        allNavLinkIds.forEach(id => {
            const link = document.getElementById(id);
            if (link) {
                // Hide if not in permissions, but always show dashboard
                if (id !== 'nav-dashboard' && !userPerms.permissions.includes(id)) {
                    link.style.display = 'none';
                }
            }
        });
        // Explicitly hide users tab for 'user' role, as it's a special case
        const usersLink = document.getElementById('nav-users');
        if(usersLink) usersLink.style.display = 'none';
    }
    const adminView = document.getElementById('admin-view');
    const showSignupLink = document.getElementById('show-signup-link');
    const showLoginLink = document.getElementById('show-login-link');

    if (showSignupLink) {
        showSignupLink.addEventListener('click', (e) => {
            e.preventDefault();
            if (loginView && signupView) {
                loginView.classList.add('hidden');
                signupView.classList.remove('hidden');
            }
        });
    }

    if (showLoginLink) {
        showLoginLink.addEventListener('click', (e) => {
            e.preventDefault();
            if (loginView && signupView) {
                signupView.classList.add('hidden');
                loginView.classList.remove('hidden');
            }
        });
    }

    function getBubbleStyles(sender) {
        switch (sender) {
            case 'bot':
                return 'bg-blue-500 text-white';
            case 'system':
                return 'bg-yellow-200 text-yellow-800';
            case 'user':
                return 'bg-red-500 text-white';
            case 'admin':
                return 'bg-green-500 text-white';
            default:
                return 'bg-gray-300 dark:bg-gray-600';
        }
    }
    const loginForm = document.getElementById('login-form');
    const logoutButton = document.getElementById('logout-button');
    const navLinks = { dashboard: document.getElementById('nav-dashboard'), users: document.getElementById('nav-users'), unanswered: document.getElementById('nav-unanswered'), answered: document.getElementById('nav-answered'), library: document.getElementById('nav-library'), notifications: document.getElementById('nav-notifications'), chats: document.getElementById('nav-chats'), archives: document.getElementById('nav-archives'), settings: document.getElementById('nav-settings'), connections: document.getElementById('nav-connections'), flows: document.getElementById('nav-flows') };
    const pages = { dashboard: document.getElementById('dashboard-page'), users: document.getElementById('users-page'), unanswered: document.getElementById('unanswered-page'), answered: document.getElementById('answered-page'), library: document.getElementById('library-page'), notifications: document.getElementById('notifications-page'), chats: document.getElementById('chats-page'), archives: document.getElementById('archives-page'), settings: document.getElementById('settings-page'), connections: document.getElementById('connections-page'), flows: document.getElementById('flows-page') };
    const answerModal = document.getElementById('answer-modal');
    const modalQuestionText = document.getElementById('modal-question-text');
    const modalAnswerTextarea = document.getElementById('modal-answer-textarea');
    const modalSaveBtn = document.getElementById('modal-save-btn');
    const modalCancelBtn = document.getElementById('modal-cancel-btn');
    const editLibraryModal = document.getElementById('edit-library-modal');
    const editModalIntentName = document.getElementById('edit-modal-intent-name');
    const editModalResponsesTextarea = document.getElementById('edit-modal-responses-textarea');
    const editModalSaveBtn = document.getElementById('edit-modal-save-btn');
    const editModalCancelBtn = document.getElementById('edit-modal-cancel-btn');
    let currentResponseToEdit = null;
    let statsChart = null;

    function showToast(message, type = 'success') {
        const toast = document.getElementById('toast-notification');
        toast.textContent = message;
        toast.className = `toast show ${type}`;
        setTimeout(() => { toast.className = 'toast'; }, 3000);
    }

    async function updateNotificationBadge() {
        try {
            const data = await apiRequest('/api/notifications');
            const requestCount = data.items.filter(n => n.type === 'human_request' && n.status !== 'closed').length;

            const navLink = document.getElementById('nav-notifications');
            let badge = navLink.querySelector('.notification-badge');

            if (requestCount > 0) {
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'notification-badge';
                    navLink.appendChild(badge);
                }
                badge.textContent = requestCount;
            } else {
                if (badge) {
                    badge.remove();
                }
            }
        } catch (error) {
            console.error("Bildirim rozeti güncellenirken hata oluştu:", error);
        }
    }

    async function apiRequest(url, method = 'GET', body = null) {
        const headers = { 'Content-Type': 'application/json' };
        if (window.API_TOKEN) {
            headers['Authorization'] = `Bearer ${window.API_TOKEN}`;
        }
        const options = { method, headers: headers };
        if (body) options.body = JSON.stringify(body);
        const response = await fetch(url, options);
        if (response.status === 401) {
            window.location.reload();
            throw new Error("Oturum süresi doldu veya yetki hatası.");
        }
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: 'Bilinmeyen bir hata oluştu' }));
            throw new Error(errorData.message);
        }
        return response.status === 204 ? null : response.json();
    }

    function switchPage(pageName) {
        Object.values(pages).forEach(p => p.classList.add('hidden'));
        Object.values(navLinks).forEach(l => l.classList.remove('active'));
        pages[pageName].classList.remove('hidden');
        navLinks[pageName].classList.add('active');
        const loadFunction = window[`load${pageName.charAt(0).toUpperCase() + pageName.slice(1)}`];
        if (loadFunction) loadFunction();
    }

    function setupCheckboxListeners(containerId, selectAllId, ...buttons) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const selectAll = document.getElementById(selectAllId);
        if (!selectAll) return;

        const listener = () => {
            const checkedCount = container.querySelectorAll('.item-checkbox:checked').length;
            buttons.forEach(btn => { if(btn) btn.disabled = checkedCount === 0 });
            const totalCheckboxes = container.querySelectorAll('.item-checkbox').length;
            selectAll.checked = totalCheckboxes > 0 && checkedCount === totalCheckboxes;
        };
        container.addEventListener('change', e => { if (e.target.classList.contains('item-checkbox')) listener(); });
        selectAll.addEventListener('change', () => {
            container.querySelectorAll('.item-checkbox').forEach(cb => cb.checked = selectAll.checked);
            listener();
        });
    }

    async function handleDeleteSelected(containerId, url, loadFunction, idKey = 'questions') {
        const container = document.getElementById(containerId);
        if (!container) return;
        const checked = Array.from(container.querySelectorAll('.item-checkbox:checked'));
        if (checked.length === 0) return;
        if (!confirm(`${checked.length} ögeyi silmek istediğinizden emin misiniz?`)) return;
        const ids = checked.map(cb => cb.dataset.id);
        try {
            await apiRequest(url, 'DELETE', { [idKey]: ids });
            showToast('Seçilen ögeler silindi.');
            loadFunction();
        } catch (error) { showToast(`Hata: ${error.message}`, 'error'); }
    }

    window.loadChats = async function () {
        const listEl = document.getElementById('active-chats-list');
        if (!listEl) { console.error("HATA: 'active-chats-list' ID'li element bulunamadı!"); return; }
        try {
            const sessions = await apiRequest('/api/active_chats');
            if (sessions.length === 0) {
                listEl.innerHTML = '<p class="text-center text-gray-500 py-4">Şu anda aktif bir sohbet bulunmuyor.</p>';
                return;
            }
            listEl.innerHTML = sessions.map(session => `
                <div class="card p-4 rounded-lg flex items-center justify-between gap-3">
                    <div class="flex-1">
                        <p><strong>Kullanıcı ID:</strong> ${session.user_id}</p>
                        <p class="text-sm text-gray-500"><strong>Oturum ID:</strong> ${session.sid}</p>
                        ${session.chat_type ? `<p class="text-sm text-gray-500"><strong>Sohbet Türü:</strong> ${session.chat_type}</p>` : ''}
                        <p class="text-sm text-gray-500"><strong>Başlangıç:</strong> ${new Date(session.start_time).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' })}</p>
                    </div>
                    <button class="join-chat-btn px-4 py-2 text-sm font-medium text-white bg-blue-500 rounded-lg hover:bg-blue-600" data-sid="${session.sid}">Sohbete Katıl</button>
                </div>
            `).join('');
        } catch (error) {
            listEl.innerHTML = `<p class="text-red-500">Aktif sohbetler yüklenemedi: ${error.message}</p>`;
        }
    };

    window.loadDashboard = async function () {
        try {
            const stats = await apiRequest('/api/dashboard-stats');
            document.getElementById('stat-library').textContent = stats.library_count;
            document.getElementById('stat-unanswered').textContent = stats.unanswered_count;
            document.getElementById('stat-answered').textContent = stats.answered_count;
            const ctx = document.getElementById('stats-chart').getContext('2d');
            if (statsChart) statsChart.destroy();
            statsChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Kütüphane', 'Cevaplanmamış', 'Cevaplanmış'],
                    datasets: [{ data: [stats.library_count, stats.unanswered_count, stats.answered_count], backgroundColor: ['#4F46E5', '#EF4444', '#EAB308'] }]
                },
                options: { responsive: true, plugins: { legend: { position: 'top' } } }
            });
        } catch (error) { console.error(`Dashboard verileri yüklenemedi: ${error.message}`); }
    };

    window.loadUnanswered = async function (page = 1, search = null) {
        const listEl = document.getElementById('questions-list');
        if (!listEl) { console.error("HATA: 'questions-list' ID'li element bulunamadı!"); return; }
        const searchTerm = search !== null ? search : (document.getElementById('search-unanswered')?.value || '');
        try {
            const url = `/api/unanswered?page=${page}&search=${encodeURIComponent(searchTerm)}`;
            const data = await apiRequest(url);
            listEl.innerHTML = data.items.length === 0
                ? '<p class="text-gray-500 text-center py-4">Sonuç bulunamadı.</p>'
                : data.items.map(q => `
                    <div class="card p-4 rounded-lg flex items-center gap-3">
                        <input type="checkbox" class="item-checkbox h-5 w-5" data-id="${q}">
                        <p class="flex-1">${q}</p>
                        <button class="answer-btn px-3 py-1 text-sm font-medium text-white bg-blue-500 rounded-lg hover:bg-blue-600" data-question="${q}">Cevapla</button>
                    </div>
                `).join('');
            renderPagination('pagination-unanswered', data.total_pages, data.current_page, 'loadUnanswered', searchTerm);
        } catch (error) { listEl.innerHTML = `<p class="text-red-500">Hata: ${error.message}</p>`; }
    };

    window.loadAnswered = async function (page = 1, search = null) {
        const listEl = document.getElementById('answered-list');
        if (!listEl) { console.error("HATA: 'answered-list' ID'li element bulunamadı!"); return; }
        const searchTerm = search !== null ? search : (document.getElementById('search-answered')?.value || '');
        try {
            const url = `/api/answered?page=${page}&search=${encodeURIComponent(searchTerm)}`;
            const data = await apiRequest(url);
            listEl.innerHTML = data.items.length === 0
                ? '<p class="text-gray-500 text-center py-4">Sonuç bulunamadı.</p>'
                : data.items.map(item => `
                    <div class="card p-4 rounded-lg flex items-center gap-3">
                        <input type="checkbox" class="item-checkbox h-5 w-5" data-id="${item.id}">
                        <div class="flex-1"><p><strong>Soru:</strong> ${item.question}</p><p><strong>Cevap:</strong> ${item.answer}</p></div>
                    </div>
                `).join('');
            renderPagination('pagination-answered', data.total_pages, data.current_page, 'loadAnswered', searchTerm);
        } catch (error) { listEl.innerHTML = `<p class="text-red-500">Hata: ${error.message}</p>`; }
    };

    window.loadLibrary = async function (page = 1, search = null) {
        const listEl = document.getElementById('library-list');
        if (!listEl) { console.error("HATA: 'library-list' ID'li element bulunamadı!"); return; }
        const searchTerm = search !== null ? search : (document.getElementById('search-library')?.value || '');
        try {
            const url = `/api/library?page=${page}&search=${encodeURIComponent(searchTerm)}`;
            const data = await apiRequest(url);
            const entries = Object.entries(data.items);
            listEl.innerHTML = entries.length === 0
                ? '<p class="text-gray-500 text-center py-4">Sonuç bulunamadı.</p>'
                : entries.map(([responseId, group]) => `
                    <div class="card p-4 rounded-lg mb-4 flex items-start gap-4">
                        <input type="checkbox" class="item-checkbox h-5 w-5 mt-1" data-response-id="${responseId}" data-intents='${JSON.stringify(group.intents)}'>
                        <div class="flex-1">
                            <div class="flex justify-between items-start mb-3 pb-3 border-b border-gray-200 dark:border-gray-700">
                                <div>
                                    <strong class="text-lg">Cevap Grubu (ID: ${responseId})</strong>
                                    <ul class="list-disc list-inside pl-4 mt-2">
                                        ${(group.responses || []).map(r => `<li>${r}</li>`).join('')}
                                    </ul>
                                    ${group.bubbles && group.bubbles.length > 0 ? `
                                        <div class="mt-2">
                                            <strong>Baloncuklar:</strong>
                                            <div class="flex flex-wrap gap-2 mt-1">
                                                ${(group.bubbles || []).map(b => `<span class="bg-indigo-200 text-indigo-900 text-xs font-medium px-2.5 py-0.5 rounded dark:bg-cyan-700 dark:text-cyan-200">${b.text}</span>`).join('')}
                                            </div>
                                        </div>
                                    ` : ''}
                                    ${group.action ? `
                                        <div class="mt-2">
                                            <strong>Eylem:</strong>
                                            <div class="flex flex-wrap gap-2 mt-1">
                                                <span class="font-mono text-sm bg-purple-200 text-purple-900 dark:bg-purple-700 dark:text-purple-200 px-2 py-1 rounded">${translate(group.action)}</span>
                                            </div>
                                        </div>
                                    ` : ''}
                                </div>
                                <button class="edit-response-group-btn px-3 py-1 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700" data-group='${JSON.stringify({response_id: responseId, response_data: group})}'>Düzenle</button>
                            </div>
                            <div class="space-y-2">
                                <strong class="text-md">Bu Cevabı Tetikleyen Niyetler:</strong>
                                <div class="flex flex-wrap gap-2 pl-4">
                                    ${(group.intents || []).map(intentKey => `<span class="font-mono text-sm bg-emerald-200 text-emerald-900 dark:bg-green-700 dark:text-green-200 px-2 py-1 rounded">${intentKey}</span>`).join('')}
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('');
            renderPagination('pagination-library', data.total_pages, data.current_page, 'loadLibrary', searchTerm);
        } catch (error) { listEl.innerHTML = `<p class="text-red-500">Hata: ${error.message}</p>`; }
    };

    window.loadNotifications = async function (page = 1, search = null) {
        const listEl = document.getElementById('notifications-list');
        if (!listEl) { console.error("HATA: 'notifications-list' ID'li element bulunamadı!"); return; }
        const searchTerm = search !== null ? search : (document.getElementById('search-notifications')?.value || '');
        try {
            const url = `/api/notifications?page=${page}&search=${encodeURIComponent(searchTerm)}`;
            const data = await apiRequest(url);
            listEl.innerHTML = data.items.length === 0
                ? '<p class="text-gray-500 text-center py-4">Sonuç bulunamadı.</p>'
                : data.items.map(item => {
                    const isHumanRequest = item.type === 'human_request';
                    const isUnanswered = item.type === 'unanswered_question';

                    let cardClass = 'card';
                    let iconHtml;
                    let clickableProps = '';
                    let actionHtml = '';
                    let messageClass = '';

                    const tooltipData = `
                        data-username="${item.user_name || 'Bilinmiyor'}"
                        data-chatid="${item.chat_display_id || 'Yok'}"
                        data-timestamp="${new Date(item.timestamp).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' })}"
                    `;

                    if (isHumanRequest) {
                        iconHtml = `
                            <div class="tooltip-trigger mr-3" ${tooltipData}>
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                            </div>
                        `;
                        if (item.status === 'closed') {
                            cardClass = 'bg-red-200 dark:bg-red-900/50 border-red-700';
                            actionHtml = '<span class="text-sm font-medium text-red-700 dark:text-red-300">Silinmiş</span>';
                            clickableProps = ''; // Not clickable
                            messageClass = 'text-gray-500 dark:text-gray-400 line-through';
                        } else {
                            cardClass = 'bg-orange-100 dark:bg-orange-900 border-orange-500 hover:bg-orange-200 dark:hover:bg-orange-800 cursor-pointer';
                            clickableProps = `data-sid="${item.sid}"`;
                            actionHtml = '<button class="px-3 py-1 text-sm font-medium text-white bg-blue-500 rounded-lg hover:bg-blue-600">Sohbete Git</button>';
                            messageClass = 'font-semibold text-orange-800 dark:text-orange-200';
                        }
                    } else {
                        iconHtml = `
                            <div class="tooltip-trigger mr-3" ${tooltipData}>
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            </div>
                        `;

                        if (isUnanswered) {
                            if (item.is_deleted) {
                                cardClass = 'bg-red-200 dark:bg-red-900/50 border-red-700';
                                actionHtml = '<span class="text-sm font-medium text-red-700 dark:text-red-300">Silinmiş</span>';
                            } else {
                                cardClass = 'card';
                            }
                        }
                    }

                    return `
                    <div class="${cardClass} p-4 rounded-lg flex items-center gap-3 border notification-item" ${clickableProps}>
                        <input type="checkbox" class="item-checkbox h-5 w-5" data-id="${item.id}">
                        ${iconHtml}
                        <div class="flex-1">
                            <p class="${messageClass}">${item.message}</p>
                            <p class="text-sm text-gray-500 dark:text-gray-400">${new Date(item.timestamp).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' })}</p>
                        </div>
                        ${actionHtml}
                    </div>
                    `;
                }).join('');
            renderPagination('pagination-notifications', data.total_pages, data.current_page, 'loadNotifications', searchTerm);
        } catch (error) { listEl.innerHTML = `<p class="text-red-500">Hata: ${error.message}</p>`; }
    };

    window.loadArchive = async function (page = 1, search = null) {
        const listEl = document.getElementById('archive-list');
        if (!listEl) { console.error("HATA: 'archive-list' ID'li element bulunamadı!"); return; }
        const searchTerm = search !== null ? search : (document.getElementById('search-archive')?.value || '');
        try {
            const url = `/api/archived_chats?page=${page}&search=${encodeURIComponent(searchTerm)}`;
            const data = await apiRequest(url);
            listEl.innerHTML = data.items.length === 0
                ? '<p class="text-gray-500 text-center py-4">Arşivde sonuç bulunamadı.</p>'
                : data.items.map(item => `
                    <div class="card p-4 rounded-lg flex items-center gap-4">
                        <input type="checkbox" class="item-checkbox h-5 w-5" data-id="${item.chat_display_id}">
                        <div class="flex-1 cursor-pointer view-archive-btn" data-id="${item.chat_display_id}">
                            ${item.chat_type ? `<p class="text-sm"><strong>Sohbet Türü:</strong> <span class="font-semibold ${item.chat_type === 'Sipariş Bilgisi' ? 'text-blue-600' : 'text-green-600'}">${item.chat_type}</span></p>` : ''}
                            <p><strong>Sohbet ID:</strong> <span class="font-mono">${item.chat_display_id}</span></p>
                            <p class="text-sm"><strong>Kullanıcı:</strong> ${item.user_name || item.user_id}</p>
                        </div>
                        <div class="text-right">
                            <p class="text-sm text-gray-500">${new Date(item.start_time).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' })}</p>
                            <span class="text-xs font-semibold text-white bg-gray-500 px-2 py-1 rounded-full">${item.history.length} mesaj</span>
                        </div>
                    </div>
                `).join('');
            renderPagination('pagination-archive', data.total_pages, data.current_page, 'loadArchive', searchTerm);
        } catch (error) { listEl.innerHTML = `<p class="text-red-500">Hata: ${error.message}</p>`; }
    };

    window.loadPrechatArchive = async function (page = 1, search = null) {
        const listEl = document.getElementById('prechat-archive-list');
        if (!listEl) { console.error("HATA: 'prechat-archive-list' ID'li element bulunamadı!"); return; }
        const searchTerm = search !== null ? search : (document.getElementById('search-prechat-archive')?.value || '');
        try {
            const url = `/api/prechat_submissions?page=${page}&search=${encodeURIComponent(searchTerm)}`;
            const data = await apiRequest(url);
            if (data.items.length === 0) {
                listEl.innerHTML = '<p class="text-gray-500 text-center py-4">Arşivde sonuç bulunamadı.</p>';
            } else {
                const prechatSettings = await apiRequest('/api/settings/prechat');
                const questionMap = new Map((prechatSettings.questions || []).map(q => [q.id, q.text]));

                listEl.innerHTML = data.items.map(item => {
                    const detailsHtml = Object.entries(item)
                        .filter(([key]) => key !== 'submission_id' && key !== 'user_id' && key !== 'timestamp')
                        .map(([key, value]) => `<p class="text-sm"><strong>${questionMap.get(key) || key}:</strong> ${value}</p>`)
                        .join('');

                    return `
                    <div class="card p-4 rounded-lg flex items-start gap-4">
                        <input type="checkbox" class="item-checkbox h-5 w-5 mt-1" data-id="${item.submission_id}">
                        <div class="flex-1">
                            <p><strong>Kullanıcı ID:</strong> <span class="font-mono">${item.user_id}</span></p>
                            <div class="mt-2">${detailsHtml}</div>
                        </div>
                        <div class="text-right">
                            <p class="text-sm text-gray-500">${new Date(item.timestamp).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' })}</p>
                        </div>
                    </div>
                `}).join('');
            }
            renderPagination('pagination-prechat-archive', data.total_pages, data.current_page, 'loadPrechatArchive', searchTerm);
        } catch (error) {
            listEl.innerHTML = `<p class="text-red-500">Hata: ${error.message}</p>`;
        }
    };

    window.loadSurveyArchive = async function (page = 1, search = null) {
        const listEl = document.getElementById('survey-archive-list');
        if (!listEl) { console.error("HATA: 'survey-archive-list' ID'li element bulunamadı!"); return; }
        const searchTerm = search !== null ? search : (document.getElementById('search-survey-archive')?.value || '');
        try {
            const url = `/api/survey_submissions?page=${page}&search=${encodeURIComponent(searchTerm)}`;
            const data = await apiRequest(url);
            if (data.items.length === 0) {
                listEl.innerHTML = '<p class="text-gray-500 text-center py-4">Arşivde sonuç bulunamadı.</p>';
            } else {
                const surveySettings = await apiRequest('/api/settings/survey');
                const questionMap = new Map((surveySettings.questions || []).map(q => [q.id, q.text]));

                listEl.innerHTML = data.items.map(item => {
                    const detailsHtml = Object.entries(item)
                        .filter(([key]) => !['submission_id', 'timestamp', 'chat_session_id', 'chat_display_id'].includes(key))
                        .map(([key, value]) => `<p class="text-sm"><strong>${questionMap.get(key) || key}:</strong> ${value}</p>`)
                        .join('');

                    return `
                    <div class="card p-4 rounded-lg flex items-start gap-4">
                        <input type="checkbox" class="item-checkbox h-5 w-5 mt-1" data-id="${item.submission_id}">
                        <div class="flex-1">
                            <p><strong>Sohbet ID:</strong> <span class="font-mono">${item.chat_display_id || item.chat_session_id}</span></p>
                            <div class="mt-2">${detailsHtml}</div>
                        </div>
                        <div class="text-right">
                            <p class="text-sm text-gray-500">${new Date(item.timestamp).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' })}</p>
                        </div>
                    </div>
                `}).join('');
            }
            renderPagination('pagination-survey-archive', data.total_pages, data.current_page, 'loadSurveyArchive', searchTerm);
        } catch (error) {
            listEl.innerHTML = `<p class="text-red-500">Hata: ${error.message}</p>`;
        }
    };

    window.loadArchives = async function () {
        const tabButtons = document.querySelectorAll('#archives-page button[data-tab]');
        const tabContents = document.querySelectorAll('#archives-tab-content > div');

        function switchTab(tabName) {
            tabContents.forEach(content => {
                content.classList.add('hidden');
            });
            const activeTab = document.getElementById(`${tabName}-tab`);
            if(activeTab) activeTab.classList.remove('hidden');

            tabButtons.forEach(button => {
                if (button.dataset.tab === tabName) {
                    button.classList.add('border-b-2', 'border-blue-500', 'text-blue-600');
                    button.classList.remove('text-gray-500');
                } else {
                    button.classList.remove('border-b-2', 'border-blue-500', 'text-blue-600');
                    button.classList.add('text-gray-500');
                }
            });
        }

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                switchTab(button.dataset.tab);
            });
        });

        // Load content for all tabs initially
        loadArchive();
        loadPrechatArchive();
        loadSurveyArchive();

        // Activate the first tab by default
        switchTab('chat-archive');
    };

    window.loadSettings = async function () {
        const tabButtons = document.querySelectorAll('#settings-page button[data-tab]');
        const tabContents = document.querySelectorAll('#settings-tab-content > div:not(#preview-tab)');

        function switchTab(tabName) {
            tabContents.forEach(content => {
                content.classList.add('hidden');
            });
            document.getElementById(`${tabName}-tab`).classList.remove('hidden');

            tabButtons.forEach(button => {
                if (button.dataset.tab === tabName) {
                    button.classList.add('border-b-2', 'border-blue-500', 'text-blue-600');
                    button.classList.remove('text-gray-500');
                } else {
                    button.classList.remove('border-b-2', 'border-blue-500', 'text-blue-600');
                    button.classList.add('text-gray-500');
                }
            });
        }

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                switchTab(button.dataset.tab);
            });
        });

        // --- Pre-chat Settings Logic ---
        function setupPreChatForm() {
            const questionsContainer = document.getElementById('prechat-questions-container');
            const addQuestionBtn = document.getElementById('add-prechat-question');
            const questionTemplate = document.getElementById('question-template');
            const optionTemplate = document.getElementById('option-template');

            if (!questionsContainer || !addQuestionBtn || !questionTemplate || !optionTemplate) return;

            function addOption(optionsContainer, optionText = '') {
                const optionClone = optionTemplate.content.cloneNode(true);
                const optionItem = optionClone.querySelector('.option-item');
                optionItem.querySelector('.option-text').value = optionText;
                optionItem.querySelector('.remove-option-btn').addEventListener('click', () => {
                    optionItem.remove();
                });
                optionsContainer.appendChild(optionClone);
            }

            function addPrechatQuestion(question = { id: `q${crypto.randomUUID()}`, text: '', type: 'text', required: false, options: [] }) {
                const questionClone = questionTemplate.content.cloneNode(true);
                const questionItem = questionClone.querySelector('.question-item');
                questionItem.dataset.id = question.id;

                const textInput = questionClone.querySelector('.question-text');
                textInput.value = question.text;
                // Add required attribute logic here if needed in the future

                const typeSelect = questionClone.querySelector('.question-type');
                typeSelect.value = question.type;

                const optionsContainer = questionClone.querySelector('.options-container');
                const addOptionBtn = questionClone.querySelector('.add-option-btn');

                function toggleOptionsUI() {
                    const isMultipleChoice = typeSelect.value === 'multiple-choice';
                    optionsContainer.classList.toggle('hidden', !isMultipleChoice);
                    addOptionBtn.classList.toggle('hidden', !isMultipleChoice);
                }

                typeSelect.addEventListener('change', toggleOptionsUI);
                addOptionBtn.addEventListener('click', () => addOption(optionsContainer));

                if (question.type === 'multiple-choice' && question.options) {
                    question.options.forEach(opt => addOption(optionsContainer, opt));
                }

                const removeBtn = questionClone.querySelector('.remove-question-btn');
                removeBtn.addEventListener('click', () => {
                    questionItem.remove();
                });

                questionsContainer.appendChild(questionClone);
                toggleOptionsUI();
            }

            async function loadPreChatForm() {
                try {
                    const settings = await apiRequest('/api/settings/prechat');
                    document.getElementById('prechat-enabled').checked = settings.enabled || false;
                    questionsContainer.innerHTML = ''; // Clear previous questions

                    if (settings.questions && settings.questions.length > 0) {
                        settings.questions.forEach(q => addPrechatQuestion(q));
                    } else {
                        addPrechatQuestion(); // Add one default question if none exist
                    }
                } catch (error) {
                    showToast(`Pre-chat ayarları yüklenemedi: ${error.message}`, 'error');
                    addPrechatQuestion(); // Add a default question on error
                }
            }

            if (addQuestionBtn && !addQuestionBtn.dataset.listenerAttached) {
                addQuestionBtn.addEventListener('click', () => addPrechatQuestion());
                addQuestionBtn.dataset.listenerAttached = 'true';
            }

            // Initial load
            loadPreChatForm();
        }

        const savePrechatBtn = document.getElementById('save-prechat-settings');
        if (savePrechatBtn && !savePrechatBtn.dataset.listenerAttached) {
            savePrechatBtn.addEventListener('click', async () => {
                const enabled = document.getElementById('prechat-enabled').checked;
                const questions = [];
                document.querySelectorAll('#prechat-questions-container .question-item').forEach((item, index) => {
                    const text = item.querySelector('.question-text').value.trim();
                    const type = item.querySelector('.question-type').value;
                    if (text) {
                        const question = {
                            id: item.dataset.id || `q${index + 1}`,
                            text: text,
                            type: type,
                            required: false, // Add logic for this if a 'required' checkbox is added to the template
                            options: []
                        };
                        if (type === 'multiple-choice') {
                            const optionInputs = item.querySelectorAll('.option-text');
                            optionInputs.forEach(optInput => {
                                const optText = optInput.value.trim();
                                if(optText) {
                                    question.options.push(optText);
                                }
                            });
                        }
                        questions.push(question);
                    }
                });

                try {
                    await apiRequest('/api/settings/prechat', 'POST', { enabled, questions });
                    showToast('Pre-chat ayarları başarıyla kaydedildi.');
                } catch (error) {
                    showToast(`Hata: ${error.message}`, 'error');
                }
            });
            savePrechatBtn.dataset.listenerAttached = 'true';
        }

        async function loadThemeForm() {
            try {
                const settings = await apiRequest('/api/settings/theme');
                // Global
                document.getElementById('theme-primary-color').value = settings.primary_color || '#4F46E5';
                document.getElementById('theme-font').value = settings.font || 'Inter';
                document.getElementById('theme-font-size').value = (settings.font_size || '14').replace('px', '');
                document.getElementById('theme-bot-name').value = settings.bot_name || 'Destek Chatbot';

                // Light Mode
                document.getElementById('theme-page-bg-color-light').value = settings.page_bg_color_light || '#F3F4F6';
                document.getElementById('theme-chat-bg-color-light').value = settings.chat_bg_color_light || '#FFFFFF';
                document.getElementById('theme-input-bg-color-light').value = settings.input_bg_color_light || '#FFFFFF';
                document.getElementById('theme-input-text-color-light').value = settings.input_text_color_light || '#1F2937';
                document.getElementById('theme-user-bubble-color-light').value = settings.user_bubble_color_light || '#4F46E5';
                document.getElementById('theme-user-text-color-light').value = settings.user_text_color_light || '#FFFFFF';
                document.getElementById('theme-bot-bubble-color-light').value = settings.bot_bubble_color_light || '#E5E7EB';
                document.getElementById('theme-bot-text-color-light').value = settings.bot_text_color_light || '#1F2937';

                // Dark Mode
                document.getElementById('theme-page-bg-color-dark').value = settings.page_bg_color_dark || '#111827';
                document.getElementById('theme-chat-bg-color-dark').value = settings.chat_bg_color_dark || '#1F2937';
                document.getElementById('theme-input-bg-color-dark').value = settings.input_bg_color_dark || '#374151';
                document.getElementById('theme-input-text-color-dark').value = settings.input_text_color_dark || '#F9FAFB';
                document.getElementById('theme-user-bubble-color-dark').value = settings.user_bubble_color_dark || '#4F46E5';
                document.getElementById('theme-user-text-color-dark').value = settings.user_text_color_dark || '#FFFFFF';
                document.getElementById('theme-bot-bubble-color-dark').value = settings.bot_bubble_color_dark || '#374151';
                document.getElementById('theme-bot-text-color-dark').value = settings.bot_text_color_dark || '#F9FAFB';

                const iconPreview = document.getElementById('bot-icon-preview');
                const iconPath = settings.bot_icon_path ? `static/${settings.bot_icon_path}` : 'static/default_bot_icon.png';
                iconPreview.src = `/${iconPath}?v=${new Date().getTime()}`;

                const currentCustomFont = document.getElementById('current-custom-font');
                if (currentCustomFont) {
                    if (settings.custom_font_path) {
                        currentCustomFont.textContent = `${settings.custom_font_family || 'CustomFont'} (${settings.custom_font_path.split('/').pop()})`;
                    } else {
                        currentCustomFont.textContent = 'Yok';
                    }
                }
                const fontFamilyNameInput = document.getElementById('font-family-name');
                if(fontFamilyNameInput) fontFamilyNameInput.value = settings.custom_font_family || '';

                updateChatPreview(); // Call without args, it will read from inputs
            } catch (error) {
                showToast(`Tema ayarları yüklenemedi: ${error.message}`, 'error');
            }
        }

        // --- Theme form event listeners ---
        const themeInputs = document.querySelectorAll('#theme-form input, #theme-form select');
        themeInputs.forEach(input => {
            if (input.type === 'file') return; // Skip file input, it has its own listener
            const eventType = input.type === 'color' || input.type === 'number' ? 'input' : 'change';
            input.addEventListener(eventType, () => updateChatPreview());
        });

        const previewToggle = document.getElementById('preview-theme-toggle');
        if(previewToggle) {
            previewToggle.addEventListener('change', () => updateChatPreview());
        }

        const botIconInput = document.getElementById('theme-bot-icon');
        if(botIconInput) {
            botIconInput.addEventListener('change', () => {
                const file = botIconInput.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        document.getElementById('bot-icon-preview').src = e.target.result;
                        updateChatPreview();
                    };
                    reader.readAsDataURL(file);
                }
            });
        }

        const saveThemeBtn = document.getElementById('save-theme-settings');
        if(saveThemeBtn) {
            saveThemeBtn.addEventListener('click', async () => {
                const form = document.getElementById('theme-form');
                const formData = new FormData(form);

                try {
                    // We need a special API request function for FormData
                    const response = await fetch('/api/settings/theme', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${window.API_TOKEN}`
                        },
                        body: formData
                    });
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.message);
                    }
                    const result = await response.json();
                    showToast(result.message);

                    // Update the preview dynamically
                    updateChatPreview(result.new_settings);

                } catch (error) {
                    showToast(`Hata: ${error.message}`, 'error');
                }
            });
        }

        function updateChatPreview() {
            const isDarkPreview = document.getElementById('preview-theme-toggle').checked;
            const previewContainer = document.getElementById('chat-preview-container');

            previewContainer.style.backgroundColor = isDarkPreview ? '#111827' : '#F3F4F6';

            const settings = {
                primary_color: document.getElementById('theme-primary-color').value,
                font: document.getElementById('theme-font').value,
                font_size: document.getElementById('theme-font-size').value,

                page_bg_color_light: document.getElementById('theme-page-bg-color-light').value,
                chat_bg_color_light: document.getElementById('theme-chat-bg-color-light').value,
                input_bg_color_light: document.getElementById('theme-input-bg-color-light').value,
                input_text_color_light: document.getElementById('theme-input-text-color-light').value,
                user_bubble_color_light: document.getElementById('theme-user-bubble-color-light').value,
                user_text_color_light: document.getElementById('theme-user-text-color-light').value,
                bot_bubble_color_light: document.getElementById('theme-bot-bubble-color-light').value,
                bot_text_color_light: document.getElementById('theme-bot-text-color-light').value,

                page_bg_color_dark: document.getElementById('theme-page-bg-color-dark').value,
                chat_bg_color_dark: document.getElementById('theme-chat-bg-color-dark').value,
                input_bg_color_dark: document.getElementById('theme-input-bg-color-dark').value,
                input_text_color_dark: document.getElementById('theme-input-text-color-dark').value,
                user_bubble_color_dark: document.getElementById('theme-user-bubble-color-dark').value,
                user_text_color_dark: document.getElementById('theme-user-text-color-dark').value,
                bot_bubble_color_dark: document.getElementById('theme-bot-bubble-color-dark').value,
                bot_text_color_dark: document.getElementById('theme-bot-text-color-dark').value,
            };

            const pageBgColor = isDarkPreview ? settings.page_bg_color_dark : settings.page_bg_color_light;
            const chatBgColor = isDarkPreview ? settings.chat_bg_color_dark : settings.chat_bg_color_light;
            const inputBgColor = isDarkPreview ? settings.input_bg_color_dark : settings.input_bg_color_light;
            const inputTextColor = isDarkPreview ? settings.input_text_color_dark : settings.input_text_color_light;
            const userBubbleColor = isDarkPreview ? settings.user_bubble_color_dark : settings.user_bubble_color_light;
            const userTextColor = isDarkPreview ? settings.user_text_color_dark : settings.user_text_color_light;
            const botBubbleColor = isDarkPreview ? settings.bot_bubble_color_dark : settings.bot_bubble_color_light;
            const botTextColor = isDarkPreview ? settings.bot_text_color_dark : settings.bot_text_color_light;

            previewContainer.style.backgroundColor = pageBgColor;

            const previewHeader = document.getElementById('chat-preview-header');
            if (previewHeader) previewHeader.style.backgroundColor = settings.primary_color;

            const previewBotName = document.getElementById('chat-preview-bot-name');
            if (previewBotName) previewBotName.textContent = document.getElementById('theme-bot-name').value || 'Destek Chatbot';

            const previewMessages = document.getElementById('chat-preview-messages');
            if (previewMessages) {
                previewMessages.style.backgroundColor = chatBgColor;
                previewMessages.style.fontFamily = settings.font;
                previewMessages.style.fontSize = `${settings.font_size}px`;
            }

            const previewFooter = document.getElementById('chat-preview-footer');
            const previewInput = document.getElementById('chat-preview-input');
            if (previewFooter) previewFooter.style.backgroundColor = pageBgColor;
            if (previewInput) {
                previewInput.style.backgroundColor = inputBgColor;
                previewInput.style.color = inputTextColor;
            }

            const previewUserBubble = document.getElementById('chat-preview-user-bubble');
            if (previewUserBubble) {
                previewUserBubble.style.backgroundColor = userBubbleColor;
                previewUserBubble.style.color = userTextColor;
            }

            const previewBotBubbles = document.querySelectorAll('.chat-preview-bot-bubble');
            previewBotBubbles.forEach(b => {
                b.style.backgroundColor = botBubbleColor;
                b.style.color = botTextColor;
            });

            const botIconPreview = document.getElementById('bot-icon-preview');
            const chatPreviewBotIcon = document.getElementById('chat-preview-bot-icon');
            if (chatPreviewBotIcon) {
                chatPreviewBotIcon.src = botIconPreview.src;
            }
        }

        async function loadCannedResponsesForm() {
            try {
                const settings = await apiRequest('/api/settings/canned_responses');
                const fields = [
                    'welcome', 'fallback', 'human_request_sending', 'human_request_queued',
                    'admin_connecting', 'admin_joined', 'admin_left', 'admin_closed_chat',
                    'user_id_request', 'intent_process_error', 'unknown_intent_response'
                ];
                fields.forEach(field => {
                    const el = document.getElementById(`canned-${field.replace(/_/g, '-')}`);
                    if (el) {
                        el.value = settings[field] || '';
                    }
                });

                // Handle the toggle switch separately
                const getIdToggle = document.getElementById('canned-get-id-from-chat');
                if (getIdToggle) {
                    getIdToggle.checked = settings.get_id_from_chat || false;
                }

            } catch (error) {
                showToast(`Metin ayarları yüklenemedi: ${error.message}`, 'error');
            }
        }

        const cannedWelcomeInput = document.getElementById('canned-welcome');
        if(cannedWelcomeInput) {
            cannedWelcomeInput.addEventListener('input', () => {
                const previewWelcome = document.getElementById('chat-preview-welcome');
                if(previewWelcome) previewWelcome.textContent = cannedWelcomeInput.value;
            });
        }

        const cannedFallbackInput = document.getElementById('canned-fallback');
        if(cannedFallbackInput) {
            cannedFallbackInput.addEventListener('input', () => {
                const previewFallback = document.getElementById('chat-preview-fallback');
                if(previewFallback) previewFallback.textContent = cannedFallbackInput.value;
            });
        }

        const saveCannedBtn = document.getElementById('save-canned-responses-settings');
        if(saveCannedBtn) {
            saveCannedBtn.addEventListener('click', async () => {
                const fields = [
                    'welcome', 'fallback', 'human_request_sending', 'human_request_queued',
                    'admin_connecting', 'admin_joined', 'admin_left', 'admin_closed_chat',
                    'user_id_request', 'intent_process_error', 'unknown_intent_response'
                ];
                const data = {};
                fields.forEach(field => {
                    const el = document.getElementById(`canned-${field.replace(/_/g, '-')}`);
                    if (el) {
                        data[field] = el.value;
                    }
                });

                // Add the toggle value
                const getIdToggle = document.getElementById('canned-get-id-from-chat');
                if (getIdToggle) {
                    data.get_id_from_chat = getIdToggle.checked;
                }

                try {
                    await apiRequest('/api/settings/canned_responses', 'POST', data);
                    showToast('Metin ayarları başarıyla kaydedildi.');
                } catch (error) {
                    showToast(`Hata: ${error.message}`, 'error');
                }
            });
        }

        // Load the pre-chat tab by default
        switchTab('pre-chat');
        setupPreChatForm();
        loadThemeForm();
        loadCannedResponsesForm();

        // --- Survey Settings Logic ---
        const surveySettingsForm = document.getElementById('survey-settings-form');
        if (surveySettingsForm) {
            const surveyEnabledToggle = document.getElementById('survey-enabled');
            const questionsContainer = document.getElementById('survey-questions-container');
            const addQuestionBtn = document.getElementById('add-survey-question');
            const saveSurveySettingsBtn = document.getElementById('save-survey-settings');
            const questionTemplate = document.getElementById('survey-question-template');
            const optionTemplate = document.getElementById('survey-option-template');

            function addOption(optionsContainer, optionText = '') {
                if (!optionTemplate) return;
                const optionClone = optionTemplate.content.cloneNode(true);
                const optionItem = optionClone.querySelector('.survey-option-item');
                optionItem.querySelector('.option-text').value = optionText;
                optionItem.querySelector('.remove-option-btn').addEventListener('click', () => {
                    optionItem.remove();
                });
                optionsContainer.appendChild(optionClone);
            }

            function addQuestion(question = { id: `q${Date.now()}`, text: '', type: 'rating', options: [] }) {
                if (!questionTemplate) return;
                const questionClone = questionTemplate.content.cloneNode(true);
                const questionItem = questionClone.querySelector('.survey-question-item');
                questionItem.dataset.id = question.id;

                const textInput = questionClone.querySelector('.question-text');
                textInput.value = question.text;

                const typeSelect = questionClone.querySelector('.question-type');
                typeSelect.value = question.type;

                const optionsContainer = questionClone.querySelector('.options-container');
                const addOptionBtn = questionClone.querySelector('.add-option-btn');

                function toggleOptionsUI() {
                    const isMultipleChoice = typeSelect.value === 'multiple-choice';
                    optionsContainer.classList.toggle('hidden', !isMultipleChoice);
                    addOptionBtn.classList.toggle('hidden', !isMultipleChoice);
                }

                typeSelect.addEventListener('change', toggleOptionsUI);

                addOptionBtn.addEventListener('click', () => addOption(optionsContainer));

                if (question.type === 'multiple-choice' && question.options) {
                    question.options.forEach(opt => addOption(optionsContainer, opt));
                }

                const removeBtn = questionClone.querySelector('.remove-question-btn');
                removeBtn.addEventListener('click', () => {
                    questionItem.remove();
                });

                questionsContainer.appendChild(questionClone);
                toggleOptionsUI(); // Initial check
            }

            async function loadSurveySettings() {
                try {
                    const settings = await apiRequest('/api/settings/survey');

                    surveyEnabledToggle.checked = settings.enabled || false;

                    document.getElementById('survey-trigger-admin-close').checked = settings.trigger_on_admin_close || false;
                    document.getElementById('survey-trigger-user-inactive').checked = settings.trigger_on_user_inactive || false;
                    document.getElementById('survey-trigger-bot-end').checked = settings.trigger_on_bot_end || false;
                    document.getElementById('survey-trigger-phrase').checked = settings.trigger_on_phrase || false;
                    document.getElementById('survey-trigger-phrases').value = (settings.trigger_phrases || []).join('\n');

                    questionsContainer.innerHTML = ''; // Clear previous
                    if (settings.questions && settings.questions.length > 0) {
                        settings.questions.forEach(q => addQuestion(q));
                    } else {
                        addQuestion();
                    }

                    if (settings.theme) {
                        for (const [key, value] of Object.entries(settings.theme)) {
                            const input = document.getElementById(`survey-theme-${key}`);
                            if (input) {
                                input.value = value;
                            }
                        }
                    }

                } catch (error) {
                    showToast(`Anket ayarları yüklenemedi: ${error.message}`, 'error');
                    addQuestion(); // Add a default question on error
                }
            }

            if (addQuestionBtn && !addQuestionBtn.dataset.listenerAttached) {
                addQuestionBtn.addEventListener('click', () => addQuestion());
                addQuestionBtn.dataset.listenerAttached = 'true';
            }

            if (saveSurveySettingsBtn && !saveSurveySettingsBtn.dataset.listenerAttached) {
                saveSurveySettingsBtn.addEventListener('click', async () => {
                    const questions = [];
                    document.querySelectorAll('#survey-questions-container .survey-question-item').forEach((item, index) => {
                        const text = item.querySelector('.question-text').value.trim();
                        const type = item.querySelector('.question-type').value;
                        if (text) {
                            const question = {
                                id: `q${index + 1}`,
                                text: text,
                                type: type,
                                options: [] // Default empty options
                            };
                            if (type === 'rating') {
                                question.options = [1, 2, 3, 4, 5];
                            } else if (type === 'multiple-choice') {
                                const optionInputs = item.querySelectorAll('.option-text');
                                optionInputs.forEach(optInput => {
                                    const optText = optInput.value.trim();
                                    if(optText) {
                                        question.options.push(optText);
                                    }
                                });
                            }
                            questions.push(question);
                        }
                    });

                    const theme = {};
                    const themeInputs = surveySettingsForm.querySelectorAll('input[type="color"]');
                    themeInputs.forEach(input => {
                        const key = input.id.replace('survey-theme-', '');
                        theme[key] = input.value;
                    });

                    const triggerPhrases = document.getElementById('survey-trigger-phrases').value
                        .split('\n')
                        .map(p => p.trim())
                        .filter(p => p);

                    const settings = {
                        enabled: surveyEnabledToggle.checked,
                        trigger_on_admin_close: document.getElementById('survey-trigger-admin-close').checked,
                        trigger_on_user_inactive: document.getElementById('survey-trigger-user-inactive').checked,
                        trigger_on_bot_end: document.getElementById('survey-trigger-bot-end').checked,
                        trigger_on_phrase: document.getElementById('survey-trigger-phrase').checked,
                        trigger_phrases: triggerPhrases,
                        questions: questions,
                        theme: theme
                    };

                    try {
                        await apiRequest('/api/settings/survey', 'POST', settings);
                        showToast('Anket ayarları başarıyla kaydedildi.');
                    } catch (error) {
                        showToast(`Hata: ${error.message}`, 'error');
                    }
                });
                saveSurveySettingsBtn.dataset.listenerAttached = 'true';
            }

            // Only load if the settings page is active and the survey tab is visible
            if (document.getElementById('settings-page').classList.contains('hidden') === false) {
                 loadSurveySettings();
            }
        }
    };

    let currentChatSessionId = null;
    window.loadChats = async function() {
        const listEl = document.getElementById('active-chats-list');
        // window.socket'in varlığını ve bağlı olup olmadığını kontrol et
        if (!listEl || !window.socket || !window.socket.connected) {
            // Henüz bağlı değilse, listeyi temizle ve bekle
            listEl.innerHTML = '<p class="text-gray-500">Bağlantı kuruluyor...</p>';
            return;
        }

        try {
            const allSessions = await apiRequest('/api/active_chats');
            const adminSid = window.socket.id;

            const relevantSessions = allSessions.filter(session => {
                const hasAdmins = session.admin_sids && session.admin_sids.length > 0;
                // 1. Henüz bir adminin katılmadığı (bekleyen) sohbetleri göster
                if (!hasAdmins) {
                    return true;
                }
                // 2. Bu adminin zaten katılmış olduğu sohbetleri göster
                return session.admin_sids.includes(adminSid);
            });

            listEl.innerHTML = relevantSessions.length === 0
                ? '<p class="text-gray-500">Görüntülenecek aktif sohbet bulunmuyor.</p>'
                : relevantSessions.map(session => `
                    <div class="chat-list-item p-3 rounded-lg cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700 flex justify-between items-center" data-sid="${session.sid}" data-display-id="${session.chat_display_id || session.sid}">
                        <div>
                            <p class="font-semibold">Kullanıcı: ${session.user_name || session.user_id}</p>
                            <p class="text-sm text-gray-500">Sohbet ID: ${session.chat_display_id || session.sid}</p>
                            ${session.chat_type ? `<p class="text-sm text-gray-500"><strong>Sohbet Türü:</strong> ${session.chat_type}</p>` : ''}
                            <p class="text-sm text-gray-500">Başlangıç: ${new Date(session.start_time).toLocaleTimeString('tr-TR', { timeZone: 'Europe/Istanbul' })}</p>
                        </div>
                        ${
                            session.human_request_active
                            ? '<span class="text-xs font-semibold text-white bg-red-500 px-2 py-1 rounded-full animate-pulse">İstek</span>'
                            : (session.admin_sids && session.admin_sids.includes(adminSid)
                                ? '<span class="text-xs font-semibold text-white bg-blue-500 px-2 py-1 rounded-full">Katıldınız</span>'
                                : '<span class="text-xs font-semibold text-white bg-green-500 px-2 py-1 rounded-full">Bekliyor</span>')
                        }
                    </div>
                `).join('');
        } catch (error) {
            listEl.innerHTML = `<p class="text-red-500">Hata: ${error.message}</p>`;
        }
    };

    async function openChatWindow(sessionId, displayId) {
        if (!sessionId) return;
        currentChatSessionId = sessionId;

        document.getElementById('no-chat-selected').classList.add('hidden');
        const chatWindow = document.getElementById('chat-window');
        chatWindow.classList.remove('hidden');
        document.getElementById('chat-user-id').textContent = displayId || sessionId;

        const historyEl = document.getElementById('chat-history');
        historyEl.innerHTML = '<p>Yükleniyor...</p>';

        try {
            const history = await apiRequest(`/api/chat/${sessionId}`);
            historyEl.innerHTML = history.map(msg => {
                const alignment = msg.sender === 'admin' ? 'text-right' : 'text-left';
                const bubbleClasses = getBubbleStyles(msg.sender);
                return `
                    <div class="mb-2 ${alignment}">
                        <p class="font-bold text-sm capitalize text-gray-700 dark:text-gray-300">${msg.sender}</p>
                        <p class="inline-block p-2 rounded-lg ${bubbleClasses}">${msg.text}</p>
                        <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">${new Date(msg.timestamp).toLocaleTimeString('tr-TR', { timeZone: 'Europe/Istanbul' })}</p>
                    </div>
                `;
            }).join('');
            historyEl.scrollTop = historyEl.scrollHeight;
        } catch (error) {
            historyEl.innerHTML = `<p class="text-red-500">Sohbet geçmişi yüklenemedi: ${error.message}</p>`;
        }
    }

    document.getElementById('active-chats-list')?.addEventListener('click', e => {
        const item = e.target.closest('.chat-list-item');
        if (item) {
            const sessionId = item.dataset.sid;
            const displayId = item.dataset.displayId;
            // Adminin bu sohbete katıldığını sunucuya bildir
            if (window.socket) {
                window.socket.emit('admin_join_chat', { user_sid: sessionId });
            }
            openChatWindow(sessionId, displayId);
        }
    });

    document.getElementById('admin-send-btn')?.addEventListener('click', () => {
        const input = document.getElementById('admin-chat-input');
        const text = input.value.trim();
        if (text && currentChatSessionId && window.socket) {
            window.socket.emit('admin_message', { user_sid: currentChatSessionId, text: text });
            input.value = '';
        }
    });

    document.getElementById('admin-chat-input')?.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            document.getElementById('admin-send-btn').click();
        }
    });

    document.getElementById('leave-chat-btn')?.addEventListener('click', () => {
        if (currentChatSessionId && window.socket) {
            if (confirm('Bu sohbetten ayrılıp kullanıcıyı bota geri aktarmak istediğinizden emin misiniz?')) {
                const sidToLeave = currentChatSessionId;
                window.socket.emit('admin_leave_chat', { user_sid: sidToLeave });
            }
        }
    });

    document.getElementById('close-chat-btn')?.addEventListener('click', () => {
        if (currentChatSessionId && window.socket) {
            if (confirm('Bu sohbeti tamamen sonlandırmak istediğinizden emin misiniz? Bu işlem geri alınamaz.')) {
                const sidToClose = currentChatSessionId;
                window.socket.emit('admin_close_chat', { user_sid: sidToClose });
            }
        }
    });

    document.getElementById('notifications-list')?.addEventListener('click', e => {
        const item = e.target.closest('.notification-item');
        if (item && item.dataset.sid) {
            const sessionId = item.dataset.sid;
            switchPage('chats');
            // Give the page a moment to become visible before trying to open the window
            setTimeout(() => {
                if (window.socket) {
                    window.socket.emit('admin_join_chat', { user_sid: sessionId });
                }
                openChatWindow(sessionId);
            }, 100);
        }
    });

    function openAnswerModal(question) {
        currentQuestionToAnswer = question;
        modalQuestionText.textContent = `Soru: "${question}"`;
        modalAnswerTextarea.value = '';
        answerModal.classList.remove('hidden');
    }

    function closeAnswerModal() {
        answerModal.classList.add('hidden');
        currentQuestionToAnswer = null;
    }

    document.getElementById('questions-list')?.addEventListener('click', e => {
        if (e.target.classList.contains('answer-btn')) openAnswerModal(e.target.dataset.question);
    });

    modalCancelBtn?.addEventListener('click', closeAnswerModal);
    modalSaveBtn?.addEventListener('click', async () => {
        const answer = modalAnswerTextarea.value.trim();
        if (!answer) {
            showToast('Cevap alanı boş bırakılamaz.', 'error');
            return;
        }

        // Optimistically close modal and give feedback
        const questionToAnswer = currentQuestionToAnswer; // Capture the variable
        closeAnswerModal();
        showToast('Cevap kaydediliyor...');

        try {
            await apiRequest('/api/answer', 'POST', { question: questionToAnswer, answer });
            showToast('Cevap başarıyla kaydedildi.', 'success');
            loadUnanswered();
        } catch (error) {
            showToast(`Hata: "${questionToAnswer}" sorusuna cevap kaydedilemedi. ${error.message}`, 'error');
            // Note: The modal is already closed. For a better UX, we might reopen it
            // with the typed answer, but for now, a clear error message is sufficient.
        }
    });

    // Cevapla modalı için Enter ile kaydetme, Shift+Enter ile yeni satır ekleme
    modalAnswerTextarea?.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Yeni satır oluşturmayı engelle
            modalSaveBtn.click(); // Kaydet butonunu tetikle
        }
    });

    logoutButton?.addEventListener('click', () => {
        window.location.href = '/logout';
    });

    Object.keys(navLinks).forEach(pageName => {
        if(navLinks[pageName]) {
            navLinks[pageName].addEventListener('click', (e) => {
                e.preventDefault();
                switchPage(pageName);
            });
        }
    });

    setupCheckboxListeners('questions-list', 'select-all-unanswered', document.getElementById('delete-selected-unanswered-btn'));
    setupCheckboxListeners('answered-list', 'select-all-answered', document.getElementById('delete-selected-answered-btn'), document.getElementById('train-selected-btn'), document.getElementById('train-group-btn'));
    setupCheckboxListeners('library-list', 'select-all-library', document.getElementById('delete-selected-library-btn'), document.getElementById('regroup-selected-library-btn'));
    setupCheckboxListeners('notifications-list', 'select-all-notifications', document.getElementById('delete-selected-notifications-btn'));
    setupCheckboxListeners('archive-list', 'select-all-archive', document.getElementById('delete-selected-archive-btn'));
    setupCheckboxListeners('prechat-archive-list', 'select-all-prechat-archive', document.getElementById('delete-selected-prechat-btn'));
    setupCheckboxListeners('survey-archive-list', 'select-all-survey-archive', document.getElementById('delete-selected-survey-btn'));

    document.getElementById('delete-selected-unanswered-btn')?.addEventListener('click', () => handleDeleteSelected('questions-list', '/api/unanswered', loadUnanswered, 'questions'));
    document.getElementById('delete-selected-answered-btn')?.addEventListener('click', () => handleDeleteSelected('answered-list', '/api/answered', loadAnswered, 'ids'));
    document.getElementById('delete-selected-archive-btn')?.addEventListener('click', () => handleDeleteSelected('archive-list', '/api/archived_chats', loadArchive, 'chat_ids'));
    document.getElementById('delete-selected-prechat-btn')?.addEventListener('click', () => handleDeleteSelected('prechat-archive-list', '/api/prechat_submissions', loadPrechatArchive, 'submission_ids'));
    document.getElementById('delete-selected-survey-btn')?.addEventListener('click', () => handleDeleteSelected('survey-archive-list', '/api/survey_submissions', loadSurveyArchive, 'submission_ids'));

    // Kütüphane silme işlemi artık response_id bazında çalışır
    document.getElementById('delete-selected-library-btn')?.addEventListener('click', async () => {
        const listEl = document.getElementById('library-list');
        const checked = Array.from(listEl.querySelectorAll('.item-checkbox:checked'));
        if (checked.length === 0) return;

        const responseIdsToDelete = checked.map(cb => cb.dataset.responseId);
        if (!confirm(`${responseIdsToDelete.length} cevap grubunu silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.`)) return;

        try {
            for (const responseId of responseIdsToDelete) {
                await apiRequest('/api/library', 'DELETE', { response_id: responseId });
            }
            showToast(`${responseIdsToDelete.length} grup başarıyla silindi.`);
            loadLibrary(); // Refresh the list
        } catch (error) {
            showToast(`Hata: ${error.message}`, 'error');
        }
    });

    document.getElementById('delete-selected-notifications-btn')?.addEventListener('click', () => handleDeleteSelected('notifications-list', '/api/notifications', loadNotifications, 'ids'));
    
    document.getElementById('train-selected-btn')?.addEventListener('click', async () => {
        const button = document.getElementById('train-selected-btn');
        const checked = Array.from(document.getElementById('answered-list').querySelectorAll('.item-checkbox:checked'));
        if (checked.length === 0) return;
        const ids = checked.map(cb => cb.dataset.id);
        button.disabled = true;
        button.textContent = 'Eğitiliyor...';
        try {
            const result = await apiRequest('/api/train', 'POST', { ids });
            showToast(result.message);
            loadAnswered(1, document.getElementById('search-answered')?.value || '');
        } catch (error) {
            showToast(`Hata: ${error.message}`, 'error');
        } finally {
            button.disabled = false;
            button.textContent = 'Kütüphaneye Ekle';
        }
    });

    document.getElementById('search-unanswered')?.addEventListener('input', debounce(() => loadUnanswered(1, document.getElementById('search-unanswered').value), 300));
    document.getElementById('search-answered')?.addEventListener('input', debounce(() => loadAnswered(1, document.getElementById('search-answered').value), 300));
    document.getElementById('search-library')?.addEventListener('input', debounce(() => loadLibrary(1, document.getElementById('search-library').value), 300));
    document.getElementById('search-notifications')?.addEventListener('input', debounce(() => loadNotifications(1, document.getElementById('search-notifications').value), 300));
    document.getElementById('search-archive')?.addEventListener('input', debounce(() => loadArchive(1, document.getElementById('search-archive').value), 300));
    document.getElementById('search-prechat-archive')?.addEventListener('input', debounce(() => loadPrechatArchive(1, document.getElementById('search-prechat-archive').value), 300));
    document.getElementById('search-survey-archive')?.addEventListener('input', debounce(() => loadSurveyArchive(1, document.getElementById('search-survey-archive').value), 300));

    const archiveModal = document.getElementById('archive-chat-modal');
    const archiveModalCloseBtn = document.getElementById('archive-modal-close-btn');

    function openArchiveModal(chatData) {
        const detailsEl = document.getElementById('archive-modal-details');
        const historyEl = document.getElementById('archive-modal-history');

        detailsEl.innerHTML = `
            ${chatData.chat_type ? `<p><strong>Sohbet Türü:</strong> <span class="font-semibold">${chatData.chat_type}</span></p>` : ''}
            <p><strong>Sohbet ID:</strong> ${chatData.chat_display_id}</p>
            <p><strong>Kullanıcı:</strong> ${chatData.user_name || chatData.user_id}</p>
            <p><strong>Başlangıç:</strong> ${new Date(chatData.start_time).toLocaleString('tr-TR')}</p>
        `;

        historyEl.innerHTML = chatData.history.map(msg => {
            const alignment = msg.sender === 'admin' ? 'text-right' : 'text-left';
            const bubbleClasses = getBubbleStyles(msg.sender);
            return `
                <div class="mb-2 ${alignment}">
                    <p class="font-bold text-sm capitalize text-gray-700 dark:text-gray-300">${msg.sender}</p>
                    <p class="inline-block p-2 rounded-lg ${bubbleClasses}">${msg.text}</p>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">${new Date(msg.timestamp).toLocaleTimeString('tr-TR')}</p>
                </div>
            `;
        }).join('');
        historyEl.scrollTop = historyEl.scrollHeight;

        archiveModal.classList.remove('hidden');
    }

    function closeArchiveModal() {
        archiveModal.classList.add('hidden');
    }

    archiveModalCloseBtn?.addEventListener('click', closeArchiveModal);

    document.getElementById('archive-list')?.addEventListener('click', async e => {
        const item = e.target.closest('.view-archive-btn');
        if (item) {
            const chatId = item.dataset.id;
            try {
                const chatData = await apiRequest(`/api/archived_chats/${chatId}`);
                openArchiveModal(chatData);
            } catch (error) {
                showToast(`Arşivlenmiş sohbet yüklenemedi: ${error.message}`, 'error');
            }
        }
    });


    if (adminView) {
        // Load critical data like action names as soon as the admin view is confirmed
        loadActionNames().then(() => {
            // Now that names are loaded, switch to the initial page
            switchPage('dashboard');
        });

        // Connect to WebSocket server
        const socket = io();
        window.socket = socket; // Make socket globally accessible

        socket.on('connect', () => {
            console.log('Successfully connected to WebSocket server.');
            // Let the server know this is an admin client
            socket.emit('admin_connect');
            // Update badge on initial connection
            updateNotificationBadge();
        });

        socket.on('disconnect', () => {
            showToast('Real-time connection lost. Trying to reconnect...', 'error');
        });


        socket.on('new_message', (data) => {
            // Gelen mesajın şu an açık olan sohbete ait olup olmadığını kontrol et
            if (data.user_sid === currentChatSessionId && document.getElementById('chats-page').offsetParent !== null) {
                const historyEl = document.getElementById('chat-history');
                const msgEl = document.createElement('div');
                const sender = data.sender || 'bot';
                const messageText = data.text || data.response;
                const alignment = sender === 'admin' ? 'text-right' : 'text-left';
                const bubbleClasses = getBubbleStyles(sender);

                msgEl.className = `mb-2 ${alignment}`;
                msgEl.innerHTML = `
                    <p class="font-bold text-sm capitalize text-gray-700 dark:text-gray-300">${sender}</p>
                    <p class="inline-block p-2 rounded-lg ${bubbleClasses}">${messageText}</p>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">${new Date(data.timestamp).toLocaleTimeString('tr-TR', { timeZone: 'Europe/Istanbul' })}</p>
                `;
                historyEl.appendChild(msgEl);
                historyEl.scrollTop = historyEl.scrollHeight;
            }
        });

        socket.on('new_message_for_admin', (data) => {
            // Notify admin about a new message in a chat
            showToast(`Yeni mesaj: ${data.user_sid}`, 'success');
            // Optionally highlight the chat in the list
            const chatItem = document.querySelector(`.chat-list-item[data-sid="${data.user_sid}"]`);
            if (chatItem) {
                chatItem.classList.add('font-bold', 'bg-yellow-200');
            }
        });

        socket.on('chat_closed', (data) => {
            if (data.user_sid === currentChatSessionId) {
                document.getElementById('chat-window').classList.add('hidden');
                document.getElementById('no-chat-selected').classList.remove('hidden');
                currentChatSessionId = null;
            }
            // Listeyi yenilemek için `loadChats` çağrılabilir veya sadece o öğeyi listeden kaldırabiliriz.
            // Şimdilik basitçe listeyi yenileyelim.
            loadChats();
        });

        socket.on('data_changed', (data) => {
            if (!data || !data.type) return;

            const pageName = data.type;
            const activeLink = document.querySelector('.nav-link.active');
            const activePageName = activeLink ? activeLink.id.replace('nav-', '') : null;

            // Refresh the relevant page if it's currently active
            if (pageName === activePageName) {
                const loadFunction = window[`load${pageName.charAt(0).toUpperCase() + pageName.slice(1)}`];
                if (loadFunction) {
                    const paginationContainer = document.getElementById(`pagination-${pageName}`);
                    const currentPage = paginationContainer?.querySelector('.pagination-btn.bg-blue-500')?.dataset.page || 1;
                    const searchInput = document.getElementById(`search-${pageName}`);

                    if (document.activeElement !== searchInput) {
                         const searchTerm = searchInput?.value || '';
                         loadFunction(currentPage, searchTerm);
                    }
                }
            }

            // Special case: If unanswered questions change, the notifications page might need to update too.
            if (pageName === 'unanswered' && activePageName === 'notifications') {
                const paginationContainer = document.getElementById('pagination-notifications');
                const currentPage = paginationContainer?.querySelector('.pagination-btn.bg-blue-500')?.dataset.page || 1;
                const searchInput = document.getElementById('search-notifications');
                const searchTerm = searchInput?.value || '';

                if (document.activeElement !== searchInput) {
                    console.log("Unanswered questions changed, refreshing notifications list.");
                    loadNotifications(currentPage, searchTerm);
                }
            }

            // Always refresh dashboard stats if they might have changed
            if (['unanswered', 'answered', 'library', 'dashboard'].includes(pageName)) {
                 if (activePageName === 'dashboard' || !activeLink) { // Also load if on login page
                    loadDashboard();
                 }
            }

            // Always update the notification badge if notifications data has changed
            if (pageName === 'notifications') {
                updateNotificationBadge();
            }
        });

        socket.on('active_chats_updated', () => {
            const activeLink = document.querySelector('.nav-link.active');
            const activePageName = activeLink ? activeLink.id.replace('nav-', '') : null;
            // If the user is currently on the 'chats' page, reload the list.
            if (activePageName === 'chats') {
                loadChats();
            }
        });
    }

    const testEmailBtn = document.getElementById('test-email-btn');
    const testEmailStatus = document.getElementById('test-email-status');

    if (testEmailBtn) {
        testEmailBtn.addEventListener('click', async () => {
            testEmailStatus.textContent = 'Gönderiliyor...';
            testEmailStatus.style.color = '#6B7280';
            testEmailBtn.disabled = true;
            try {
                const result = await apiRequest('/api/test-email', 'POST');
                testEmailStatus.textContent = result.message;
                testEmailStatus.style.color = '#10B981';
                showToast(result.message, 'success');
            } catch (error) {
                testEmailStatus.textContent = `Hata: ${error.message}`;
                testEmailStatus.style.color = '#EF4444';
                showToast(`Hata: ${error.message}`, 'error');
            } finally {
                testEmailBtn.disabled = false;
            }
        });
    }

    const sidebarToggle = document.getElementById('sidebar-toggle');
    const body = document.body;
    const themeToggle = document.getElementById('theme-toggle');
    const themeIconLight = document.getElementById('theme-icon-light');
    const themeIconDark = document.getElementById('theme-icon-dark');

    function applyTheme(theme) {
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
            themeIconLight.classList.add('hidden');
            themeIconDark.classList.remove('hidden');
        } else {
            document.documentElement.classList.remove('dark');
            themeIconLight.classList.remove('hidden');
            themeIconDark.classList.add('hidden');
        }
    }

    sidebarToggle?.addEventListener('click', () => {
        body.classList.toggle('sidebar-collapsed');
    });

    themeToggle?.addEventListener('click', () => {
        const isDark = document.documentElement.classList.toggle('dark');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        applyTheme(isDark ? 'dark' : 'light');
    });

    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);

    function renderPagination(containerId, totalPages, currentPage, loadFunction, search = '') {
        const container = document.getElementById(containerId);
        if (!container) { return; }
        container.innerHTML = '';
        if (totalPages <= 1) return;
    
        currentPage = parseInt(currentPage, 10);
        totalPages = parseInt(totalPages, 10);
    
        let paginationHtml = '<nav class="flex justify-center items-center space-x-2">';
    
        // Önceki butonu
        paginationHtml += `<button class="pagination-nav-btn px-4 py-2 rounded-md text-sm bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 hover:bg-gray-300 ${currentPage === 1 ? 'opacity-50 cursor-not-allowed' : ''}" data-page="${currentPage - 1}" data-loadfunc="${loadFunction}" data-search="${search || ''}" ${currentPage === 1 ? 'disabled' : ''}>Önceki</button>`;
    
        // Sayfa numaraları mantığı
        const maxPagesToShow = 5;
        let startPage, endPage;
    
        if (totalPages <= maxPagesToShow) {
            startPage = 1;
            endPage = totalPages;
        } else {
            const maxPagesBeforeCurrent = Math.floor(maxPagesToShow / 2);
            const maxPagesAfterCurrent = Math.ceil(maxPagesToShow / 2) - 1;
            if (currentPage <= maxPagesBeforeCurrent) {
                startPage = 1;
                endPage = maxPagesToShow;
            } else if (currentPage + maxPagesAfterCurrent >= totalPages) {
                startPage = totalPages - maxPagesToShow + 1;
                endPage = totalPages;
            } else {
                startPage = currentPage - maxPagesBeforeCurrent;
                endPage = currentPage + maxPagesAfterCurrent;
            }
        }
    
        if (startPage > 1) {
            paginationHtml += `<button class="pagination-btn px-4 py-2 rounded-md text-sm bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 hover:bg-gray-300" data-page="1" data-loadfunc="${loadFunction}" data-search="${search || ''}">1</button>`;
            if (startPage > 2) {
                paginationHtml += `<span class="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">...</span>`;
            }
        }
    
        for (let i = startPage; i <= endPage; i++) {
            const activeClass = i === currentPage ? 'bg-blue-500 text-white' : 'bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 hover:bg-gray-300';
            paginationHtml += `<button class="pagination-btn px-4 py-2 rounded-md text-sm ${activeClass}" data-page="${i}" data-loadfunc="${loadFunction}" data-search="${search || ''}">${i}</button>`;
        }
    
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationHtml += `<span class="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">...</span>`;
            }
            paginationHtml += `<button class="pagination-btn px-4 py-2 rounded-md text-sm bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 hover:bg-gray-300" data-page="${totalPages}" data-loadfunc="${loadFunction}" data-search="${search || ''}">${totalPages}</button>`;
        }
    
        // Sonraki butonu
        paginationHtml += `<button class="pagination-nav-btn px-4 py-2 rounded-md text-sm bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 hover:bg-gray-300 ${currentPage === totalPages ? 'opacity-50 cursor-not-allowed' : ''}" data-page="${currentPage + 1}" data-loadfunc="${loadFunction}" data-search="${search || ''}" ${currentPage === totalPages ? 'disabled' : ''}>Sonraki</button>`;
    
        paginationHtml += '</nav>';
        container.innerHTML = paginationHtml;
    }

    document.addEventListener('click', e => {
        if (e.target.classList.contains('pagination-btn') || e.target.classList.contains('pagination-nav-btn')) {
            const page = parseInt(e.target.dataset.page, 10);
            const loadFunction = e.target.dataset.loadfunc;
            const search = e.target.dataset.search;
            if (window[loadFunction]) {
                window[loadFunction](page, search);
            }
        }
    });

    // --- Unified Edit Modal Logic ---
    const bubblesContainer = document.getElementById('edit-modal-bubbles-container');
    const intentsContainer = document.getElementById('edit-modal-intents-container');

    // Generic function to render a removable input row for bubbles
    function renderBubbleInput(container, bubble = { text: '', value: '' }) {
        const bubbleEl = document.createElement('div');
        bubbleEl.className = 'flex items-center gap-2 bubble-input-group';
        bubbleEl.innerHTML = `
            <input type="text" class="bubble-text w-1/2 px-2 py-1 border rounded-md" placeholder="Buton Metni" value="${bubble.text || ''}">
            <input type="text" class="bubble-value w-1/2 px-2 py-1 border rounded-md" placeholder="Buton Değeri" value="${bubble.value || ''}">
            <button type="button" class="remove-row-btn text-red-500 hover:text-red-700">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /></svg>
            </button>
        `;
        container.appendChild(bubbleEl);
    }

    // Generic function to render a removable input row for intents
    function renderIntentInput(container, intent = '') {
        const intentEl = document.createElement('div');
        intentEl.className = 'flex items-center gap-2 intent-input-group';
        intentEl.innerHTML = `
            <input type="text" class="intent-key w-full px-2 py-1 border rounded-md" placeholder="Niyet metni..." value="${intent || ''}">
            <button type="button" class="remove-row-btn text-red-500 hover:text-red-700">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /></svg>
            </button>
        `;
        container.appendChild(intentEl);
    }

    // Event listeners for the Edit Modal
    document.getElementById('edit-modal-add-bubble-btn')?.addEventListener('click', () => renderBubbleInput(bubblesContainer));
    document.getElementById('edit-modal-add-intent-btn')?.addEventListener('click', () => renderIntentInput(intentsContainer));
    editLibraryModal?.addEventListener('click', e => {
        if (e.target.closest('.remove-row-btn')) {
            e.target.closest('.flex').remove();
        }
    });

    async function openEditLibraryModal(group = null) {
        const actionSelect = document.getElementById('edit-modal-action');
        actionSelect.innerHTML = '<option value="">Eylem Yok</option>'; // Reset and add default

        try {
            const actions = await apiRequest('/api/actions');
            actions.forEach(action => {
                const option = document.createElement('option');
                option.value = action.id;
                option.textContent = action.name;
                actionSelect.appendChild(option);
            });
        } catch (error) {
            showToast('Eylemler yüklenemedi.', 'error');
            // Don't block the modal from opening
        }

        // If no group is passed, it's a "create" operation.
        if (group) {
            currentResponseToEdit = group.response_id;
            editModalIntentName.textContent = `Cevap Grubunu Düzenle (ID: ${group.response_id})`;
            editModalResponsesTextarea.value = (group.response_data.responses || []).join('\n');
            actionSelect.value = group.response_data.action || ''; // Set selected action
            bubblesContainer.innerHTML = '';
            (group.response_data.bubbles || []).forEach(bubble => renderBubbleInput(bubblesContainer, bubble));
            intentsContainer.innerHTML = '';
            (group.response_data.intents || []).forEach(intent => renderIntentInput(intentsContainer, intent));
        } else {
            currentResponseToEdit = null; // Ensure it's null for creation
            editModalIntentName.textContent = 'Yeni Cevap Grubu Oluştur';
            editModalResponsesTextarea.value = '';
            actionSelect.value = ''; // Reset selection
            bubblesContainer.innerHTML = '';
            intentsContainer.innerHTML = '';
            renderBubbleInput(bubblesContainer); // Add one empty bubble row
            renderIntentInput(intentsContainer); // Add one empty intent row
        }
        editLibraryModal.classList.remove('hidden');
    }

    function closeEditLibraryModal() {
        editLibraryModal.classList.add('hidden');
        currentResponseToEdit = null;
    }

    document.getElementById('library-list')?.addEventListener('click', e => {
        const editBtn = e.target.closest('.edit-response-group-btn');
        if (editBtn) {
            const groupData = JSON.parse(editBtn.dataset.group);
            openEditLibraryModal(groupData);
        }
    });

    document.getElementById('add-new-group-btn')?.addEventListener('click', () => {
        openEditLibraryModal(null); // Open in "create" mode
    });

    editModalCancelBtn?.addEventListener('click', closeEditLibraryModal);

    editModalSaveBtn?.addEventListener('click', async () => {
        const responses = editModalResponsesTextarea.value.split('\n').map(r => r.trim()).filter(r => r);
        if (responses.length === 0) {
            showToast('En az bir cevap olmalıdır.', 'error');
            return;
        }

        const bubbles = Array.from(bubblesContainer.querySelectorAll('.bubble-input-group')).map(group => {
            return {
                text: group.querySelector('.bubble-text').value.trim(),
                value: group.querySelector('.bubble-value').value.trim()
            };
        }).filter(b => b.text && b.value);

        const intents = Array.from(intentsContainer.querySelectorAll('.intent-input-group')).map(group => {
            return group.querySelector('.intent-key').value.trim();
        }).filter(i => i);

        if (intents.length === 0) {
            showToast('En az bir niyet olmalıdır.', 'error');
            return;
        }

        const action = document.getElementById('edit-modal-action').value.trim();
        const response_data = { responses, bubbles };
        if (action) {
            response_data.action = action;
        }
        const isCreating = currentResponseToEdit === null;
        const url = '/api/library';
        const method = isCreating ? 'POST' : 'PUT';
        const body = {
            response_data: response_data,
            intents: intents
        };
        if (!isCreating) {
            body.response_id = currentResponseToEdit;
        }

        try {
            await apiRequest(url, method, body);
            showToast(isCreating ? 'Grup başarıyla oluşturuldu.' : 'Cevap grubu başarıyla güncellendi.');
            closeEditLibraryModal();
            // Reload the library to show the new/updated item
            loadLibrary();
        } catch (error) {
            showToast(`Hata: ${error.message}`, 'error');
        }
    });

    // Kütüphane düzenleme modalı için Enter ile kaydetme, Shift+Enter ile yeni satır ekleme
    editModalResponsesTextarea?.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Yeni satır oluşturmayı engelle
            editModalSaveBtn.click(); // Kaydet butonunu tetikle
        }
    });

    // --- Regroup Modal Logic ---
    const regroupModal = document.getElementById('regroup-modal');
    const regroupBubblesContainer = document.getElementById('regroup-bubbles-container');
    const regroupResponsesTextarea = document.getElementById('regroup-responses-textarea');

    function openRegroupModal() {
        regroupResponsesTextarea.value = '';
        regroupBubblesContainer.innerHTML = '';
        regroupModal.classList.remove('hidden');
    }

    function closeRegroupModal() {
        regroupModal.classList.add('hidden');
    }

    document.getElementById('regroup-selected-library-btn')?.addEventListener('click', openRegroupModal);
    document.getElementById('regroup-cancel-btn')?.addEventListener('click', closeRegroupModal);
    document.getElementById('regroup-add-bubble-btn')?.addEventListener('click', () => renderBubbleInput(regroupBubblesContainer));
    regroupBubblesContainer?.addEventListener('click', e => {
        if (e.target.closest('.remove-row-btn')) {
            e.target.closest('.flex').remove();
        }
    });

    document.getElementById('regroup-save-btn')?.addEventListener('click', async () => {
        const listEl = document.getElementById('library-list');
        const checked = Array.from(listEl.querySelectorAll('.item-checkbox:checked'));
        if (checked.length === 0) {
            showToast('Lütfen en az bir cevap grubu seçin.', 'error');
            return;
        }
        const intent_keys = checked.flatMap(cb => JSON.parse(cb.dataset.intents));

        const responses = regroupResponsesTextarea.value.split('\n').map(r => r.trim()).filter(r => r);
        if (responses.length === 0) {
            showToast('En az bir ortak cevap yazılmalıdır.', 'error');
            return;
        }

        const bubbles = Array.from(regroupBubblesContainer.querySelectorAll('.bubble-input-group')).map(group => {
            return {
                text: group.querySelector('.bubble-text').value.trim(),
                value: group.querySelector('.bubble-value').value.trim()
            };
        }).filter(b => b.text && b.value);

        const response_block = { responses, bubbles };

        try {
            await apiRequest('/api/library/regroup', 'POST', { intent_keys, response_block });
            showToast(`${intent_keys.length} niyet başarıyla yeniden gruplandırıldı.`);
            closeRegroupModal();
            loadLibrary();
        } catch (error) {
            showToast(`Hata: ${error.message}`, 'error');
        }
    });

    // --- Group Train Modal Logic ---
    const groupTrainModal = document.getElementById('group-train-modal');
    const groupTrainBubblesContainer = document.getElementById('group-train-bubbles-container');
    const groupTrainResponsesTextarea = document.getElementById('group-train-responses-textarea');

    function openGroupTrainModal() {
        groupTrainResponsesTextarea.value = '';
        groupTrainBubblesContainer.innerHTML = '';
        groupTrainModal.classList.remove('hidden');
    }

    function closeGroupTrainModal() {
        groupTrainModal.classList.add('hidden');
    }

    function renderGroupTrainBubbleInput(bubble = { text: '', value: '' }) {
        const bubbleEl = document.createElement('div');
        bubbleEl.className = 'flex items-center gap-2 group-train-bubble-input-group';
        bubbleEl.innerHTML = `
            <input type="text" class="bubble-text w-1/2 px-2 py-1 border rounded-md" placeholder="Buton Metni" value="${bubble.text}">
            <input type="text" class="bubble-value w-1/2 px-2 py-1 border rounded-md" placeholder="Buton Değeri" value="${bubble.value}">
            <button type="button" class="remove-bubble-btn text-red-500 hover:text-red-700">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /></svg>
            </button>
        `;
        groupTrainBubblesContainer.appendChild(bubbleEl);
    }

    document.getElementById('train-group-btn')?.addEventListener('click', openGroupTrainModal);
    document.getElementById('group-train-cancel-btn')?.addEventListener('click', closeGroupTrainModal);
    document.getElementById('group-train-add-bubble-btn')?.addEventListener('click', () => renderGroupTrainBubbleInput());
    groupTrainBubblesContainer?.addEventListener('click', e => {
        if (e.target.closest('.remove-bubble-btn')) {
            e.target.closest('.group-train-bubble-input-group').remove();
        }
    });

    document.getElementById('group-train-save-btn')?.addEventListener('click', async () => {
        const checked = Array.from(document.getElementById('answered-list').querySelectorAll('.item-checkbox:checked'));
        if (checked.length === 0) {
            showToast('Lütfen en az bir soru seçin.', 'error');
            return;
        }
        const ids = checked.map(cb => cb.dataset.id);

        const responses = groupTrainResponsesTextarea.value.split('\n').map(r => r.trim()).filter(r => r);
        if (responses.length === 0) {
            showToast('En az bir ortak cevap yazılmalıdır.', 'error');
            return;
        }

        const bubbles = Array.from(document.querySelectorAll('.group-train-bubble-input-group')).map(group => {
            const text = group.querySelector('.bubble-text').value.trim();
            const value = group.querySelector('.bubble-value').value.trim();
            return { text, value };
        }).filter(b => b.text && b.value);

        const response_block = { responses, bubbles };

        try {
            await apiRequest('/api/train-group', 'POST', { ids, response_block });
            showToast(`${ids.length} soru başarıyla gruplandırıldı ve kütüphaneye eklendi.`);
            closeGroupTrainModal();
            loadAnswered(1, document.getElementById('search-answered')?.value || '');
        } catch (error) {
            showToast(`Hata: ${error.message}`, 'error');
        }
    });



    // --- Tooltip Logic ---
    const tooltip = document.getElementById('page-tooltip');
    const notificationsList = document.getElementById('notifications-list');

    if (tooltip && notificationsList) {
        notificationsList.addEventListener('mouseover', e => {
            const trigger = e.target.closest('.tooltip-trigger');
            if (!trigger) return;

            const username = trigger.dataset.username;
            const chatid = trigger.dataset.chatid;
            const timestamp = trigger.dataset.timestamp;

            tooltip.innerHTML = `<strong>Kullanıcı Adı:</strong> ${username}<br><strong>Sohbet ID:</strong> ${chatid}<br><strong>Tarih:</strong> ${timestamp}`;
            tooltip.style.display = 'block';
        });

        notificationsList.addEventListener('mousemove', e => {
            if (tooltip.style.display === 'block') {
                tooltip.style.left = `${e.pageX + 15}px`;
                tooltip.style.top = `${e.pageY + 15}px`;
            }
        });

        notificationsList.addEventListener('mouseout', e => {
            if (e.target.closest('.tooltip-trigger')) {
                tooltip.style.display = 'none';
            }
        });
    }

    window.loadFlows = async function() {
        const listEl = document.getElementById('flows-list');
        if (!listEl) return;
        try {
            const flows = await apiRequest('/api/flows');
            listEl.innerHTML = Object.entries(flows).map(([id, flow]) => `
                <div class="card p-4 rounded-lg">
                    <div class="flex justify-between items-center">
                        <h3 class="text-xl font-bold">${flow.name} (<span class="font-mono text-sm">${id}</span>)</h3>
                        <div>
                            <button class="edit-flow-btn px-3 py-1 text-sm font-medium text-white bg-indigo-600 rounded-lg" data-id="${id}">Düzenle</button>
                            <button class="delete-flow-btn px-3 py-1 text-sm font-medium text-white bg-red-500 rounded-lg" data-id="${id}">Sil</button>
                        </div>
                    </div>
                    <p class="text-sm text-gray-500 mt-1"><strong>Durum (State):</strong> ${translateState(flow.state_to_set)}</p>
                    <p class="text-sm text-gray-500 mt-1"><strong>Cevap İşleyici (Handler):</strong> ${translate(flow.reply_handler?.type)}</p>
                </div>
            `).join('');
        } catch (error) {
            listEl.innerHTML = `<p class="text-red-500">Hata: Akışlar yüklenemedi. ${error.message}</p>`;
        }
    };

    window.loadConnections = async function() {
        try {
            const settings = await apiRequest('/api/settings/connections');

            // Populate Email Settings
            const emailSettings = settings.email || {};
            document.getElementById('email-enabled').checked = emailSettings.enabled || false;
            document.getElementById('imap-host').value = emailSettings.imap_host || '';
            document.getElementById('imap-user').value = emailSettings.imap_user || '';
            document.getElementById('imap-password').value = emailSettings.imap_password || '';
            document.getElementById('smtp-host').value = emailSettings.smtp_host || '';
            document.getElementById('smtp-port').value = emailSettings.smtp_port || 587;
            document.getElementById('smtp-user').value = emailSettings.smtp_user || '';
            document.getElementById('smtp-password').value = emailSettings.smtp_password || '';
            document.getElementById('smtp-sender').value = emailSettings.smtp_sender || '';
            document.getElementById('notification-recipient').value = emailSettings.notification_recipient || '';

            // Populate Telegram Settings
            const telegramSettings = settings.telegram || {};
            const telegramEnabledCheckbox = document.getElementById('telegram-enabled');
            telegramEnabledCheckbox.checked = telegramSettings.enabled || false;
            document.getElementById('bot-token').value = telegramSettings.bot_token || '';
            document.getElementById('chat-id').value = telegramSettings.chat_id || '';

            // New fields for initial message and moved canned responses
            document.getElementById('telegram-initial-message').value = telegramSettings.initial_message || '';
            document.getElementById('telegram-order-info-request').value = telegramSettings.order_info_request || '';
            document.getElementById('telegram-info-request-confirmation').value = telegramSettings.info_request_confirmation || '';
            document.getElementById('telegram-service-unavailable').value = telegramSettings.telegram_service_unavailable || '';

            renderTelegramButtons(telegramSettings.buttons || []);

            // Trigger change to set initial visibility
            telegramEnabledCheckbox.dispatchEvent(new Event('change'));

        } catch (error) {
            showToast(`Bağlantı ayarları yüklenemedi: ${error.message}`, 'error');
        }
    };

    function renderTelegramButtons(buttons = []) {
        const container = document.getElementById('telegram-buttons-container');
        container.innerHTML = ''; // Clear existing buttons
        buttons.forEach(button => addTelegramButton(button.label, button.value));
    }

    function addTelegramButton(label = '', value = '') {
        const container = document.getElementById('telegram-buttons-container');
        const template = document.getElementById('telegram-button-template');
        const clone = template.content.cloneNode(true);

        const labelInput = clone.querySelector('.telegram-button-label');
        const valueInput = clone.querySelector('.telegram-button-value');
        labelInput.value = label;
        valueInput.value = value;

        const removeBtn = clone.querySelector('.remove-telegram-button-btn');
        removeBtn.addEventListener('click', (e) => {
            e.target.closest('.flex').remove();
        });

        container.appendChild(clone);
    }

    document.getElementById('add-telegram-button-btn')?.addEventListener('click', () => addTelegramButton());

    document.getElementById('telegram-enabled')?.addEventListener('change', (e) => {
        const detailsContainer = document.getElementById('telegram-initial-message-settings');
        if (e.target.checked) {
            detailsContainer.classList.remove('hidden');
        } else {
            detailsContainer.classList.add('hidden');
        }
    });

    document.getElementById('save-email-settings')?.addEventListener('click', async () => {
        const settings = {
            enabled: document.getElementById('email-enabled').checked,
            imap_host: document.getElementById('imap-host').value,
            imap_user: document.getElementById('imap-user').value,
            imap_password: document.getElementById('imap-password').value,
            smtp_host: document.getElementById('smtp-host').value,
            smtp_port: parseInt(document.getElementById('smtp-port').value, 10),
            smtp_user: document.getElementById('smtp-user').value,
            smtp_password: document.getElementById('smtp-password').value,
            smtp_sender: document.getElementById('smtp-sender').value,
            notification_recipient: document.getElementById('notification-recipient').value,
        };

        try {
            await apiRequest('/api/settings/connections/email', 'POST', settings);
            showToast('E-posta ayarları başarıyla kaydedildi.');
        } catch (error) {
            showToast(`Hata: ${error.message}`, 'error');
        }
    });

    document.getElementById('save-telegram-settings')?.addEventListener('click', async () => {
        const buttons = [];
        document.querySelectorAll('#telegram-buttons-container .flex').forEach(row => {
            const label = row.querySelector('.telegram-button-label').value.trim();
            const value = row.querySelector('.telegram-button-value').value.trim();
            if (label && value) {
                buttons.push({ label, value });
            }
        });

        const settings = {
            enabled: document.getElementById('telegram-enabled').checked,
            bot_token: document.getElementById('bot-token').value,
            chat_id: document.getElementById('chat-id').value,
            initial_message: document.getElementById('telegram-initial-message').value,
            buttons: buttons,
            order_info_request: document.getElementById('telegram-order-info-request').value,
            info_request_confirmation: document.getElementById('telegram-info-request-confirmation').value,
            telegram_service_unavailable: document.getElementById('telegram-service-unavailable').value,
        };

        try {
            await apiRequest('/api/settings/connections/telegram', 'POST', settings);
            showToast('Telegram ayarları başarıyla kaydedildi.');
        } catch (error) {
            showToast(`Hata: ${error.message}`, 'error');
        }
    });

    // --- User Management Logic ---
    const userModal = document.getElementById('user-modal');
    const userForm = document.getElementById('user-form');
    const userModalTitle = document.getElementById('user-modal-title');
    const userIdInput = document.getElementById('user-id');
    const emailInput = document.getElementById('user-email');
    const passwordInput = document.getElementById('user-password');
    const tagsInput = document.getElementById('user-tags');
    const roleSelect = document.getElementById('user-role');
    let editingUserId = null;

    window.loadUsers = async function() {
        try {
            const users = await apiRequest('/api/group_users');
            const usersList = document.getElementById('users-list');
            usersList.innerHTML = users.map(user => {
                let roleClass = '';
                let actionsHtml = '';

                if (user.role === 'group_admin') {
                    roleClass = 'bg-blue-100 text-blue-800';
                } else if (user.role === 'admin') {
                    roleClass = 'bg-green-100 text-green-800';
                } else {
                    roleClass = 'bg-yellow-100 text-yellow-800';
                    // 'user' roles can be edited and deleted by the group_admin
                    actionsHtml = `
                        <button class="edit-user-btn text-blue-600 hover:text-blue-900 mr-4" data-user='${JSON.stringify(user)}'>Düzenle</button>
                        <button class="delete-user-btn text-red-600 hover:text-red-900" data-id="${user.id}" data-email="${user.email}">Sil</button>
                    `;
                }

                const tagsHtml = (user.tags && user.tags.length > 0)
                    ? user.tags.map(tag => `<span class="bg-gray-200 text-gray-800 text-xs font-medium me-2 px-2.5 py-0.5 rounded dark:bg-gray-700 dark:text-gray-300">${tag}</span>`).join('')
                    : '<span class="text-gray-400">Etiket yok</span>';

                return `
                    <tr class="dark:hover:bg-gray-800">
                        <td class="px-6 py-4 whitespace-nowrap">${user.email}</td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${roleClass}">
                                ${user.role}
                            </span>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">${tagsHtml}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${new Date(user.created_at).toLocaleDateString('tr-TR')}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            ${actionsHtml}
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (error) {
            showToast(`Kullanıcılar yüklenemedi: ${error.message}`, 'error');
        }
    };

    function openUserModal(user = null) {
        userForm.reset();
        if (user) {
            editingUserId = user.id;
            userModalTitle.textContent = 'Kullanıcıyı Düzenle';
            userIdInput.value = user.id;
            emailInput.value = user.email;
            emailInput.disabled = true; // Don't allow email change
            passwordInput.placeholder = "Değiştirmek istemiyorsanız boş bırakın";
            tagsInput.value = (user.tags || []).join(', ');
            // Check the permissions the user has
            const userPermissions = user.permissions || [];
            document.querySelectorAll('#user-permissions input').forEach(checkbox => {
                checkbox.checked = userPermissions.includes(checkbox.value);
            });
        } else {
            editingUserId = null;
            userModalTitle.textContent = 'Yeni Kullanıcı Ekle';
            userIdInput.value = '';
            emailInput.disabled = false;
            passwordInput.placeholder = "Şifre";
            tagsInput.value = '';
             // Clear any checked permissions from last time
            document.querySelectorAll('#user-permissions input:checked').forEach(checkbox => checkbox.checked = false);
        }
        userModal.classList.remove('hidden');
    }

    function closeUserModal() {
        userModal.classList.add('hidden');
    }

    document.getElementById('add-user-btn')?.addEventListener('click', () => openUserModal());
    document.getElementById('user-modal-cancel-btn')?.addEventListener('click', closeUserModal);

    document.getElementById('users-list')?.addEventListener('click', e => {
        if (e.target.classList.contains('delete-user-btn')) {
            const userId = e.target.dataset.id;
            const email = e.target.dataset.email;
            if (confirm(`'${email}' kullanıcısını silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.`)) {
                apiRequest(`/api/group_users/${userId}`, 'DELETE')
                    .then(response => {
                        showToast(response.message, 'success');
                        loadUsers();
                    })
                    .catch(error => showToast(`Hata: ${error.message}`, 'error'));
            }
        } else if (e.target.classList.contains('edit-user-btn')) {
            const user = JSON.parse(e.target.dataset.user);
            openUserModal(user);
        }
    });

    userForm?.addEventListener('submit', async e => {
        e.preventDefault();

        const permissions = Array.from(document.querySelectorAll('#user-permissions input:checked'))
                                 .map(checkbox => checkbox.value);
        const tags = tagsInput.value.trim().split(',').map(t => t.trim()).filter(t => t);

        if (editingUserId) {
            // Edit existing user
            // For now, we only support updating tags and permissions. Password change is not handled.
            try {
                // Since there isn't a single endpoint to update everything,
                // we'll just update tags for now as per the feature request.
                const result = await apiRequest(`/api/group_users/${editingUserId}/tags`, 'PUT', { tags });
                showToast(result.message || 'Kullanıcı güncellendi.', 'success');
                closeUserModal();
                loadUsers();
            } catch (error) {
                showToast(`Hata: ${error.message}`, 'error');
            }

        } else {
            // Add new user
            const email = emailInput.value;
            const password = passwordInput.value;

            if (!password) {
                showToast('Yeni kullanıcı için şifre gereklidir.', 'error');
                return;
            }

            const body = {
                email: email,
                password: password,
                permissions: permissions,
                tags: tags
            };

            try {
                const result = await apiRequest('/api/group_users', 'POST', body);
                showToast(result.message, result.success ? 'success' : 'error');
                if(result.success) {
                    closeUserModal();
                    loadUsers();
                }
            } catch (error) {
                showToast(`Hata: ${error.message}`, 'error');
            }
        }
    });

    // --- Flow Editor Modal Logic ---
    const flowModal = document.getElementById('flow-editor-modal');
    const flowForm = document.getElementById('flow-form');
    const flowModalTitle = document.getElementById('flow-modal-title');
    const flowIdInput = document.getElementById('flow-id');
    const flowFollowUpBubblesContainer = document.getElementById('flow-follow-up-bubbles-container');
    let isCreatingFlow = false;

    function openFlowModal(flowId = null, flowData = {}) {
        isCreatingFlow = !flowId;
        flowForm.reset();
        flowFollowUpBubblesContainer.innerHTML = '';

        flowModalTitle.textContent = isCreatingFlow ? 'Yeni Akış Oluştur' : `Akışı Düzenle (${flowId})`;

        // Populate the state dropdown
        const stateSelect = document.getElementById('flow-state');
        stateSelect.innerHTML = ''; // Clear existing options
        for (const [technicalId, displayName] of Object.entries(stateTranslations)) {
            const option = document.createElement('option');
            option.value = technicalId;
            option.textContent = displayName;
            stateSelect.appendChild(option);
        }

        document.getElementById('flow-name').value = flowData.name || '';
        document.getElementById('flow-initial-prompt').value = (flowData.initial_prompt_responses || []).join('\n');
        stateSelect.value = flowData.state_to_set || 'awaiting_order_info'; // Set selected state
        document.getElementById('flow-handler-type').value = flowData.reply_handler?.type || '';

        const followUp = flowData.reply_handler?.success_follow_up || {};
        document.getElementById('flow-follow-up-responses').value = (followUp.responses || []).join('\n');
        (followUp.bubbles || []).forEach(bubble => renderBubbleInput(flowFollowUpBubblesContainer, bubble));

        flowModal.classList.remove('hidden');
    }

    function closeFlowModal() {
        flowModal.classList.add('hidden');
    }

    document.getElementById('add-new-flow-btn')?.addEventListener('click', () => openFlowModal());
    document.getElementById('flow-modal-cancel-btn')?.addEventListener('click', closeFlowModal);
    document.getElementById('flow-add-follow-up-bubble-btn')?.addEventListener('click', () => renderBubbleInput(flowFollowUpBubblesContainer));
    flowFollowUpBubblesContainer.addEventListener('click', e => {
        if (e.target.closest('.remove-row-btn')) {
            e.target.closest('.bubble-input-group').remove();
        }
    });

    document.getElementById('flows-list')?.addEventListener('click', async e => {
        if (e.target.classList.contains('edit-flow-btn')) {
            const flowId = e.target.dataset.id;
            const allFlows = await apiRequest('/api/flows');
            openFlowModal(flowId, allFlows[flowId]);
        }
        if (e.target.classList.contains('delete-flow-btn')) {
            const flowId = e.target.dataset.id;
            if (confirm(`'${flowId}' akışını silmek istediğinizden emin misiniz?`)) {
                try {
                    await apiRequest(`/api/flows/${flowId}`, 'DELETE');
                    showToast('Akış silindi.');
                    loadFlows();
                } catch (error) {
                    showToast(`Hata: ${error.message}`, 'error');
                }
            }
        }
    });

    flowForm?.addEventListener('submit', async e => {
        e.preventDefault();
        const flowName = document.getElementById('flow-name').value;
        let flowId = isCreatingFlow ? flowName.toLowerCase().replace(/\s+/g, '_') : document.getElementById('flow-id').value;
        if (!flowId) {
            showToast('Akış adı veya IDsi oluşturulamadı.', 'error');
            return;
        }

        const followUpBubbles = Array.from(flowFollowUpBubblesContainer.querySelectorAll('.bubble-input-group')).map(group => ({
            text: group.querySelector('.bubble-text').value.trim(),
            value: group.querySelector('.bubble-value').value.trim()
        })).filter(b => b.text && b.value);

        const flowData = {
            name: flowName,
            initial_prompt_responses: document.getElementById('flow-initial-prompt').value.split('\n').map(r => r.trim()).filter(r => r),
            state_to_set: document.getElementById('flow-state').value, // Directly use the value from the select
            reply_handler: {
                type: document.getElementById('flow-handler-type').value,
                success_follow_up: {
                    responses: document.getElementById('flow-follow-up-responses').value.split('\n').map(r => r.trim()).filter(r => r),
                    bubbles: followUpBubbles
                }
            }
        };

        try {
            await apiRequest(`/api/flows/${flowId}`, 'POST', flowData);
            showToast('Akış başarıyla kaydedildi.');
            closeFlowModal();
            loadFlows();
        } catch (error) {
            showToast(`Hata: ${error.message}`, 'error');
        }
    });
});
