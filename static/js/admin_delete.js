// Delete category
document.addEventListener('DOMContentLoaded', () => {

    const actionDelete = document.getElementById('action-delete-category');
    if (!actionDelete) {
        console.warn('❌ Missing element: #action-delete-category');
        return;
    }

    const categoriesData = document.getElementById('admin-categories-data');
    const categories = categoriesData ? JSON.parse(categoriesData.textContent) : [];

    const dialog = document.createElement('dialog');
    dialog.id = 'delete-category-dialog';

    const form = document.createElement('form');
    form.method = 'dialog';
    form.id = 'delete-category-form';

    const heading = document.createElement('h2');
    heading.textContent = 'Delete category';

    const formRow = document.createElement('div');
    formRow.className = 'dialog-form-row';

    const select = document.createElement('select');
    select.id = 'delete-category-select';
    select.name = 'category_id';

    const selectLabel = document.createElement('label');
    selectLabel.setAttribute('for', 'delete-category-select');
    selectLabel.textContent = 'Select category to delete:';

    formRow.append(selectLabel, select);

    const message = document.createElement('p');
    message.textContent = '⚠️ Category will be removed from all assigned channels!';

    const actions = document.createElement('div');
    actions.className = 'buttons-cancel-confirm';

    const btnCancel = document.createElement('button');
    btnCancel.type = 'button';
    btnCancel.id = 'delete-category-cancel';
    btnCancel.textContent = 'Cancel';

    const btnConfirm = document.createElement('button');
    btnConfirm.type = 'button';
    btnConfirm.id = 'delete-category-confirm';
    btnConfirm.textContent = 'Delete';

    actions.append(btnCancel, btnConfirm);
    
    form.append(heading, formRow, message, actions);
    dialog.appendChild(form);
    document.body.appendChild(dialog);

    actionDelete.addEventListener('click', () => {
        if (!categories || categories.length === 0) {
            console.warn('⚠️ No categories available for deletion');
            alert('⚠️ No categories available');
            return;
        }

        select.replaceChildren();

        categories.forEach((category) => {
            const option = document.createElement('option');
            option.value = category.category_id;
            option.textContent = category.category_name;
            select.appendChild(option);
        });

        dialog.showModal();
    });

    btnCancel.addEventListener('click', () => {
        dialog.close();
    });

    btnConfirm.addEventListener('click', async () => {
        const categoryId = select.value;

        if (!categoryId) {
            alert('⚠️ Please select a category!');
            return;
        }

        const categoryName = select.options[select.selectedIndex].text;

        if (!confirm(`⚠️ Are you sure you want to delete category "${categoryName}"?\nThis will remove it from all channels`)) {
            return;
        }

        try {
            const formData = new FormData();
            formData.append('category_id', categoryId);

            const response = await fetch('/admin/delete-category', {
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
                alert(`✅ Category "${categoryName}" deleted`);
                window.location.reload();
            }
            else {
                alert(`❌ Category "${categoryName}" not found`);
            }
        }

        catch (error) {
            console.error('❌ Delete failed:', error);
            alert(`❌ Failed to delete category "${categoryName}"`);
        }

        finally {
            dialog.close();
        }
    });

});