// Assign categories to channels
document.addEventListener('DOMContentLoaded', () => {

    // Check if reload is after category change
    const updatedChannelId = sessionStorage.getItem('updatedChannelId');
    const updatedChannelResult = sessionStorage.getItem('updatedChannelResult');

    if (updatedChannelId !== null) {
        const row = document.getElementById(`channel-${updatedChannelId}`);
        const categoryCell = row?.querySelector('.category-cell');

        // Scroll down to updated row
        if (row) {
            row.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
            });
        }

        // Flash updated cell
        if (categoryCell && updatedChannelResult !== null) {
            categoryCell.classList.add(
                updatedChannelResult === 'true' ? 'flash-cell-success' : 'flash-cell-failure'
            );

            categoryCell.addEventListener('animationend', () => {
                categoryCell.classList.remove('flash-cell-success', 'flash-cell-failure');
            }, { once: true });
        }

        sessionStorage.removeItem('updatedChannelId');
        sessionStorage.removeItem('updatedChannelResult');
    }

    // Listen for changes in category dropdown menus, update category in database and store updated channel in session
    document.querySelectorAll('.category-select').forEach((select) => {
        select.addEventListener('change', async () => {
            const formData = new FormData();
            formData.append('channel_id', select.dataset.channelId);
            formData.append('category_id', select.value);

            try {
                sessionStorage.setItem('updatedChannelId', select.dataset.channelId);

                const response = await fetch('/admin/update-assignment', {
                    method: 'POST',
                    body: formData,
                });

                if (await redirectIfUnauthorized(response)) {
                    return;
                }

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                sessionStorage.setItem('updatedChannelResult', 'true');

                window.location.reload();
            }

            catch (error) {
                sessionStorage.setItem('updatedChannelResult', 'false');
                console.error('❌ Category update failed:', error);
                alert('❌ Failed to update category.');
                window.location.reload();
            }
        });
    });

});
