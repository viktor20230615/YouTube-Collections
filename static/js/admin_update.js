// Update subscriptions
document.addEventListener('DOMContentLoaded', () => {
    const actionUpdate = document.getElementById('action-update-subscriptions');
    if (!actionUpdate) {
        console.warn('❌ Missing element: #action-update-subscriptions');
        return;
    }

    async function updateSubscriptions(confirmedUnsubscribe = false) {
        const response = await fetch('/admin/update-subscriptions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                confirmed_unsubscribe: confirmedUnsubscribe,
            }),
        });

        if (await redirectIfUnauthorized(response)) {
            return null;
        }

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        return response.json();
    }

    function normalizeUpdateResponse(data) {
        data.add_names = Array.isArray(data.add_names) ? data.add_names : [];
        data.remove_names = Array.isArray(data.remove_names) ? data.remove_names : [];
        data.total_count = Number.isInteger(data.total_count) ? data.total_count : 0;
        return data;
    }

    actionUpdate.addEventListener('click', async () => {
        // Disable button to avoid double clicks
        if (actionUpdate.disabled) {
            return;
        }
        actionUpdate.disabled = true;

        const buttonText = actionUpdate.textContent;
        actionUpdate.textContent = "Updating...";

        try {
            let data = await updateSubscriptions(false);
            if (data === null) {
                return;
            }
            data = normalizeUpdateResponse(data);

            while (data.confirmation_needed) {
                let message = "";

                if (data.add_names.length == 0) {
                    message = "ℹ️ No subscriptions to add\n";
                }
                else {
                    const addNamesToShow = data.add_names.slice(0, 10);
                    message = `ℹ️ The following ${data.add_names.length} subscriptions will be added:\n${addNamesToShow.join('\n')}\n`;
                    if (data.add_names.length > addNamesToShow.length) {
                        message += `\n...and ${data.add_names.length - addNamesToShow.length} more\n`;
                    }
                }

                if (data.remove_names.length == 0) {
                    message += "\nℹ️ No subscriptions to remove\n";
                }
                else {
                    const removeNamesToShow = data.remove_names.slice(0, 10);
                    message += `\n❌ The following ${data.remove_names.length} subscriptions will be removed:\n${removeNamesToShow.join('\n')}`;
                    if (data.remove_names.length > removeNamesToShow.length) {
                        message += `\n...and ${data.remove_names.length - removeNamesToShow.length} more\n`;
                    }
                }

                const confirmed = confirm(message);

                if (!confirmed) {
                    console.log('ℹ️ Subscriptions update cancelled');
                    return;
                }

                data = await updateSubscriptions(true);
                if (data === null) {
                    return;
                }
                data = normalizeUpdateResponse(data);
            }

            if (data.success) {
                if (data.add_names.length > 0 || data.remove_names.length > 0) {
                    let message = "✅ Updated!\n";

                    message += `\nAdded: ${data.add_names.length}\n`;
                    if (data.add_names.length > 0) {
                        const addNamesToShow = data.add_names.slice(0, 10);
                        message += `${addNamesToShow.join('\n')}`;
                        if (data.add_names.length > addNamesToShow.length) {
                            message += `\n...and ${data.add_names.length - addNamesToShow.length} more\n`;
                        }
                        message += '\n';
                    }

                    message += `\nRemoved: ${data.remove_names.length}\n`;
                    if (data.remove_names.length > 0) {
                        const removeNamesToShow = data.remove_names.slice(0, 10);
                        message += `${removeNamesToShow.join('\n')}`;
                        if (data.remove_names.length > removeNamesToShow.length) {
                            message += `\n...and ${data.remove_names.length - removeNamesToShow.length} more\n`;
                        }
                        message += '\n';
                    }

                    message += `\nCurrent subscription count: ${data.total_count}`;

                    alert(message);
                }
                else {
                    alert(
                        `ℹ️ No changes needed\n` +
                        `Still ${data.total_count} subscriptions`
                    );
                }

                window.location.reload();
                return;
            }
            else {
                alert('❌ Failed to update subscriptions');
            }
        }
        
        catch (error) {
            console.error('❌ Update error: ', error);
            alert('❌ Failed to update subscriptions');
        }
        
        finally {
            actionUpdate.disabled = false;
            actionUpdate.textContent = buttonText;
        }
    });
});