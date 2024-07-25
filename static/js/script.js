document.addEventListener('DOMContentLoaded', (event) => {
    const userIcon = document.querySelector('.user');
    const profileMenu = document.getElementById('profile-menu');

    userIcon.addEventListener('click', () => {
        if (profileMenu.style.display === 'block') {
            profileMenu.style.display = 'none';
        } else {
            profileMenu.style.display = 'block';
        }
    });

    // Hide the menu when user clicks some where else
    document.addEventListener('click', (event) => {
        if (!userIcon.contains(event.target) && !profileMenu.contains(event.target)) {
            profileMenu.style.display = 'none';
        }
    });
});

