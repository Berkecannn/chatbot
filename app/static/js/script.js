// Interactive functionality
function navigateTo(page) {
    console.log(`Navigating to ${page}`);
    // Add your navigation logic here
    // Example: window.location.href = `/${page}.html`;
}

function login() {
    console.log('Login clicked');
    // Add your login logic here
    // Example: window.location.href = '/login.html';
}

function performSearch() {
    const query = document.getElementById('searchInput').value;
    if (query.trim()) {
        console.log(`Searching for: ${query}`);
        // Add your search logic here
        // Example: window.location.href = `/search?q=${encodeURIComponent(query)}`;
        
        // Clear the input after search
        document.getElementById('searchInput').value = '';
        
        // You could show search results here
        showSearchResults(query);
    }
}

function handleSearch(event) {
    if (event.key === 'Enter') {
        performSearch();
    }
}

function selectCategory(category) {
    console.log(`Selected category: ${category}`);
    // Add category selection logic here
    // Example: window.location.href = `/category/${category}`;
    
    // Add visual feedback
    const categoryBoxes = document.querySelectorAll('.category-box');
    categoryBoxes.forEach(box => {
        if (box.onclick.toString().includes(category)) {
            box.style.transform = 'translateY(-15px) scale(1.05)';
            setTimeout(() => {
                box.style.transform = '';
            }, 300);
        }
    });
}

function showSearchResults(query) {
    // Example function to show search results
    // You can implement this based on your needs
    alert(`Searching for: "${query}"\n\nThis will be implemented with your backend search functionality.`);
}

// Add some interactive effects
document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for better UX
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });

    // Add focus management for accessibility
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('focus', function() {
            this.parentElement.style.boxShadow = '0 0 0 3px rgba(102, 126, 234, 0.3)';
        });

        searchInput.addEventListener('blur', function() {
            this.parentElement.style.boxShadow = '0 20px 40px rgba(0,0,0,0.1)';
        });
    }

    // Add keyboard navigation for categories
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            // Enhanced tab navigation
            const focusableElements = document.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            const focusedElement = document.activeElement;
            const focusedIndex = Array.from(focusableElements).indexOf(focusedElement);
            
            // Add visual focus indicators
            focusableElements.forEach((el, index) => {
                if (index === focusedIndex) {
                    el.style.outline = '2px solid #667eea';
                    el.style.outlineOffset = '2px';
                } else {
                    el.style.outline = '';
                    el.style.outlineOffset = '';
                }
            });
        }
    });

    // Add loading screen functionality
    const loadingOverlay = document.querySelector('.loading-overlay');
    if (loadingOverlay) {
        // Remove loading screen after animations complete
        setTimeout(() => {
            loadingOverlay.style.display = 'none';
        }, 3000);
    }

    // Add intersection observer for scroll animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe category boxes for scroll animations
    document.querySelectorAll('.category-box').forEach(box => {
        observer.observe(box);
    });

    // Add hover sound effects (optional - you can enable this)
    function addHoverSounds() {
        const categoryBoxes = document.querySelectorAll('.category-box');
        categoryBoxes.forEach(box => {
            box.addEventListener('mouseenter', () => {
                // Uncomment below to add hover sound
                // playHoverSound();
            });
        });
    }

    // Uncomment to enable hover sounds
    // addHoverSounds();

    // Example function for hover sound (you need to add audio files)
    function playHoverSound() {
        // const audio = new Audio('hover-sound.mp3');
        // audio.volume = 0.1;
        // audio.play().catch(e => console.log('Audio play failed:', e));
    }

    // Add custom cursor effect (optional)
    function addCustomCursor() {
        const cursor = document.createElement('div');
        cursor.style.cssText = `
            position: fixed;
            width: 20px;
            height: 20px;
            background: radial-gradient(circle, rgba(102,126,234,0.8) 0%, transparent 70%);
            border-radius: 50%;
            pointer-events: none;
            z-index: 9999;
            transition: transform 0.1s ease;
        `;
        document.body.appendChild(cursor);

        document.addEventListener('mousemove', (e) => {
            cursor.style.left = e.clientX - 10 + 'px';
            cursor.style.top = e.clientY - 10 + 'px';
        });

        // Scale cursor on interactive elements
        document.querySelectorAll('button, a, .category-box').forEach(el => {
            el.addEventListener('mouseenter', () => {
                cursor.style.transform = 'scale(2)';
            });
            el.addEventListener('mouseleave', () => {
                cursor.style.transform = 'scale(1)';
            });
        });
    }

    // Uncomment to enable custom cursor
    // addCustomCursor();
});