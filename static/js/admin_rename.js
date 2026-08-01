// Rename category
document.addEventListener('DOMContentLoaded', () => {

    const actionRename = document.getElementById('action-rename-category');
    if (!actionRename) {
        console.warn('❌ Missing element: #action-rename-category');
        return;
    }

    const categoriesData = document.getElementById('admin-categories-data');
    const categories = categoriesData ? JSON.parse(categoriesData.textContent) : [];

    const dialog = document.createElement('dialog');
    dialog.id = 'rename-category-dialog';

    const form = document.createElement('form');
    form.method = 'dialog';
    form.id = 'rename-category-form';

    const heading = document.createElement('h2');
    heading.textContent = 'Rename category';

    const message = document.createElement('p');
    message.textContent = 'Select a category to rename';

    const renameForms = document.createElement('div');
    renameForms.className = 'dialog-forms';

    const selectDiv = document.createElement('div');
    selectDiv.className = 'dialog-form-row';

    const select = document.createElement('select');
    select.id = 'rename-category-select';
    select.name = 'category_id';

    const selectLabel = document.createElement('label');
    selectLabel.setAttribute('for', 'rename-category-select');
    selectLabel.textContent = 'Category:';

    selectDiv.append(selectLabel, select);

    const inputDiv = document.createElement('div');
    inputDiv.className = 'dialog-form-row';

    const input = document.createElement('input');
    input.type = 'text';
    input.id = 'rename-category-input';
    input.name = 'category_name';

    const inputLabel = document.createElement('label');
    inputLabel.setAttribute('for', 'rename-category-input');
    inputLabel.textContent = 'New name:';

    inputDiv.append(inputLabel, input);

    renameForms.append(selectDiv, inputDiv);

    const actions = document.createElement('div');
    actions.className = 'buttons-cancel-confirm';

    const btnCancel = document.createElement('button');
    btnCancel.type = 'button';
    btnCancel.id = 'rename-category-cancel';
    btnCancel.textContent = 'Cancel';

    const btnConfirm = document.createElement('button');
    btnConfirm.type = 'button';
    btnConfirm.id = 'rename-category-confirm';
    btnConfirm.textContent = 'Rename';

    actions.append(btnCancel, btnConfirm);

    form.append(heading, message, renameForms, actions);
    dialog.appendChild(form);
    document.body.appendChild(dialog);

    actionRename.addEventListener('click', () => {
        if (!categories || categories.length === 0) {
            console.warn('⚠️ No categories available for renaming');
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

        input.value = select.options[select.selectedIndex].text;

        dialog.showModal();
    });

    select.addEventListener('change', () => {
        input.value = select.options[select.selectedIndex].text;
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

        const categoryNameOld = select.options[select.selectedIndex].text;
        const categoryNameNew = input.value.trim();

        if (!categoryNameNew) {
            alert('⚠️ Please enter a new category name!');
            return;
        }

        if (categoryNameNew === categoryNameOld) {
            alert('⚠️ Please enter a different category name!');
            return;
        }

        if (!confirm(`⚠️ Are you sure you want to rename category "${categoryNameOld}" to "${categoryNameNew}"?`)) {
            return;
        }

        try {
            const formData = new FormData();
            formData.append('category_id', categoryId);
            formData.append('category_name', categoryNameNew);

            const response = await fetch('/admin/rename-category', {
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
                alert(`✅ Category "${categoryNameOld}" renamed to "${categoryNameNew}"`);
                window.location.reload();
            }
            else {
                alert(`❌ Category "${categoryNameOld}" not found`);
            }
        }

        catch (error) {
            console.error('❌ Rename failed:', error);
            alert(`❌ Failed to rename category "${categoryNameOld}" to "${categoryNameNew}"`);
        }

        finally {
            dialog.close();
        }
    });

});