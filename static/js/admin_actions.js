document.addEventListener('DOMContentLoaded', () => {

    const toggle = document.getElementById('admin-actions-toggle');
    const menu = document.getElementById('admin-actions-menu');
    if (!toggle || !menu) {
        return;
    }

    function openMenu() {
        toggle.setAttribute('aria-expanded', 'true');
        menu.hidden = false;
    }

    function closeMenu() {
        toggle.setAttribute('aria-expanded', 'false');
        menu.hidden = true;
    }

    function toggleMenu() {
        if (toggle.getAttribute('aria-expanded') === 'true') {
            closeMenu();
        }
        else {
            openMenu();
        }
    }

    toggle.addEventListener('click', (event) => {
        event.stopPropagation();
        toggleMenu();
    });

    document.addEventListener('click', (event) => {
        if (!menu.hidden && !menu.contains(event.target) && !toggle.contains(event.target)) {
            closeMenu();
        }
    });

    window.addEventListener('scroll', () => {
        if (!menu.hidden) {
            closeMenu();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeMenu();
        }
    });

});