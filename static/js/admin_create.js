// Create category
document.addEventListener('DOMContentLoaded', () => {

    const actionCreate = document.getElementById('action-create-category');
    if (!actionCreate) {
        console.warn('❌ Missing element: #action-create-category');
        return;
    }

    actionCreate.addEventListener('click', async () => {
        const name = prompt('Enter new category name:');
        if (!name || name.trim() === '') {
            return;
        }

        const formData = new FormData();
        formData.append('category_name', name.trim());

        try {
            const response = await fetch('/admin/create-category', {
                method: 'POST',
                body: formData,
            });

            if (await redirectIfUnauthorized(response)) {
                return;
            }
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                alert(`✅ Created new category "${data.category_name}"`);
            }
            else if (data.message === 'exists') {
                alert(`ℹ️ Category "${data.category_name}" already exists!`);
            }
            else {
                alert('❌ Something went wrong');
            }

            window.location.reload();
        }

        catch (error) {
            console.error('❌ Create category error:', error);
            alert('❌ Failed to create category');
        }
    });

});