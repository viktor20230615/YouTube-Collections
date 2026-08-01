// Deal with scroll behavior of navigation bar
document.addEventListener("DOMContentLoaded", () => {

    const nav = document.querySelector(".nav-top");
    let lastScrollY = window.scrollY;
    const scrollThreshold = 20;

    window.addEventListener('scroll', () => {
        const currentScrollY = window.scrollY;
        const scrollDiff = currentScrollY - lastScrollY;

        if (scrollDiff > scrollThreshold) {
            nav.classList.add("nav-hidden");
            lastScrollY = currentScrollY;
        }
        else if (currentScrollY <= 0 || scrollDiff < -scrollThreshold) {
            nav.classList.remove("nav-hidden");
            lastScrollY = currentScrollY;
        }
    });

});