// Get time-based greeting
function getTimeBasedGreeting() {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) {
        return 'Good morning';
    } else if (hour >= 12 && hour < 18) {
        return 'Good afternoon';
    } else {
        return 'Good evening';
    }
}

// Update welcome message on page load
document.addEventListener('DOMContentLoaded', function() {
    const greeting = getTimeBasedGreeting();
    const welcomeHeaders = document.querySelectorAll('.welcome-header h1');
    welcomeHeaders.forEach(header => {
        header.textContent = header.textContent.replace('Good day', greeting);
    });
});
