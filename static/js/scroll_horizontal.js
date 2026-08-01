// Deal with scroll behavior in navigation bar
document.addEventListener('DOMContentLoaded', () => {

    const scrollContainer = document.querySelector(".nav-left-scroll");
    const scrollButtonLeft = document.querySelector(".nav-scroll-button-left");
    const scrollButtonRight = document.querySelector(".nav-scroll-button-right");

    if (!scrollContainer || !scrollButtonLeft || !scrollButtonRight) {
        console.warn("❌ Missing horizontal scroll elements");
        return;
    }

    function updateScrollButtons() {
        // total amount of possible scroll = width of content inside - visible width of box
        const ScrollContainerOverflow = scrollContainer.scrollWidth - scrollContainer.clientWidth;

        // scrollLeft = number of pixels an element's content is scrolled horizontally from left
        const canScrollLeft = scrollContainer.scrollLeft > 0;
        scrollButtonLeft.hidden = !canScrollLeft;

        // canScrollRight = amount of scroll from left < total amount of possible scroll
        const canScrollRight = scrollContainer.scrollLeft < ScrollContainerOverflow - 1;
        scrollButtonRight.hidden = !canScrollRight;
    }

    function scrollByAmount(amount) {
        scrollContainer.scrollBy({
            left: amount,
            behavior: 'smooth',
        });
    }

    scrollButtonLeft.addEventListener('click', () => {
        scrollByAmount(-160);
    });

    scrollButtonRight.addEventListener('click', () => {
        scrollByAmount(160);
    });

    scrollContainer.addEventListener('scroll', updateScrollButtons);

    window.addEventListener('resize', updateScrollButtons);

    updateScrollButtons();

});