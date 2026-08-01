document.addEventListener("DOMContentLoaded", () => {

    const button = document.getElementById("load-more-btn");
    const container = document.getElementById("videos-container");
    if (!button || !container) return;

    button.addEventListener("click", async () => {
        if (button.disabled) {
            return;
        }

        // Lock button to avoid double clicks
        button.disabled = true;
        button.textContent = "Loading...";

        try {
            // Set new filter and cursor URL parameters
            const params = new URLSearchParams();
            if (button.dataset.category) {
                params.set("category", button.dataset.category);
            }
            if (button.dataset.uncategorized === "1") {
                params.set("uncategorized", button.dataset.uncategorized);
            }
            if (button.dataset.afterPublishedAt && button.dataset.afterId) {
                params.set("after_published_at", button.dataset.afterPublishedAt);
                params.set("after_id", button.dataset.afterId);
            }

            const response = await fetch(`/subscriptions/load-more?${params.toString()}`);

            if (await redirectIfUnauthorized(response, { preserveNext: true })) {
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            // Load more videos to page
            for (const video of data.videos) {
                container.appendChild(createVideoCard(video));
            }

            // Update button
            if (data.has_more && data.last_cursor) {
                button.dataset.afterPublishedAt = data.last_cursor.after_published_at;
                button.dataset.afterId = data.last_cursor.after_id;
                button.disabled = false;
                button.textContent = "Load More";
            }
            else {
                button.remove();
            }
        }
        
        catch (error) {
            console.error("Load more failed:", error);
            button.disabled = false;
            button.textContent = "Load More";
        }
    });
    
});


function createVideoCard(video) {
    const article = document.createElement("article");
    article.className = "video-card";

    const header = document.createElement("div");
    header.className = "video-header";

    const channel = document.createElement("span");
    channel.className = "video-channel";
    channel.textContent = video.channel_name ?? "";

    const date = document.createElement("span");
    date.className = "video-date";
    date.textContent = video.published_at_display ?? "";

    header.append(channel, date);

    const link = document.createElement("a");
    link.className = "video-thumb-link";
    link.href = `https://www.youtube.com/watch?v=${encodeURIComponent(video.id ?? "")}`;
    link.target = "_blank";
    link.rel = "noopener noreferrer";

    const image = document.createElement("img");
    image.className = "video-thumb-img";
    image.src = video.thumbnail_url ?? "";
    image.alt = video.title ?? "";

    const duration = document.createElement("span");
    duration.className = "video-duration";
    duration.textContent = video.duration_display ?? "";

    link.append(image, duration);

    const title = document.createElement("div");
    title.className = "video-title";
    title.textContent = video.title ?? "";

    article.append(header, link, title);

    return article;
}