document.addEventListener("DOMContentLoaded", () => {

    const button = document.getElementById("refresh-button");
    if (!button) return;

    // Create new form for POST
    const formData = new FormData();

    if (button.dataset.category) {
        formData.append("category", button.dataset.category);
    } else if (button.dataset.uncategorized === "1") {
        formData.append("uncategorized", "1");
    }

    button.addEventListener("click", async () => {
        // Lock button to avoid double clicks
        if (button.disabled) return;
        button.disabled = true;
        const buttonText = button.textContent;
        button.textContent = "Refreshing...";

        try {
            const response = await fetch("/subscriptions/refresh", {
                method: "POST",
                body: formData,
            });

            if (await redirectIfUnauthorized(response, { preserveNext: true })) {
                return;
            }

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || "Refresh failed");
            }

            window.location.reload();
        }
        
        catch (error) {
            console.error("Refresh failed:", error);
            alert("Refresh failed. Please try again.");
            button.disabled = false;
            button.textContent = buttonText;
        }
    });
    
});
