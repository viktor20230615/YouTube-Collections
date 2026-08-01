// Sort columns
document.addEventListener('DOMContentLoaded', () => {

    // Define sort click cycles for each sortable column type
    const textSortCycle = ['none', 'asc', 'desc'];
    const dateSortCycle = ['none', 'desc', 'asc'];

    // Read current URL's sort parameters
    const searchParams = new URLSearchParams(window.location.search);
    const sortParams = searchParams.get('sort') || '';

    // Split sort parameters into an array of objects
    const sortParts = sortParams ? sortParams.split(',') : [];
    const sortRules = sortParts.map(part => {
        const [field, direction] = part.split(':');
        return { field, direction };
    });

    // Listen for clicks for every sort button
    document.querySelectorAll('.th-sort').forEach(button => {
        button.addEventListener('click', event => {
            // Prevent submitting anything for now
            event.preventDefault();

            // Determine the field whose sort button was clicked
            const th = button.closest('th');
            const clickedField = th.dataset.sortField;

            // Get current sort state for clicked field in URL sort parameters
            const currentSortRule = sortRules.find(rule => rule.field === clickedField);
            const currentSortDirection = currentSortRule?.direction || 'none';

            // Determine which sort cycle to use
            const sortCycle = 
                (clickedField === 'subscribed_at' || clickedField === 'refreshed_at') ? dateSortCycle : textSortCycle;

            // Find current direction in sort cycle and iterate it
            const currentIndex = sortCycle.indexOf(currentSortDirection);
            const safeIndex = (currentIndex === -1) ? 0 : currentIndex;
            const nextIndex = (safeIndex + 1) % sortCycle.length;
            const nextSortDirection = sortCycle[nextIndex];

            // Prepare new sort parameters for URL
            let updatedSortRules;

            // If nextSortDirection is none, remove clickedField and currentSortDirection from URL sort parameters
            if (nextSortDirection === 'none') {
                updatedSortRules = sortRules.filter(rule => rule.field !== clickedField);
            }
            // If nextSortDirection is not none and currentSortDirection is not none 
            // (clickedField already exists in current URL sort parameters), 
            // modify direction for clickedField in URL sort parameters
            else if (sortRules.some(rule => rule.field === clickedField)) {
                updatedSortRules = 
                    sortRules.map(rule => (rule.field === clickedField) ? { field: rule.field, direction: nextSortDirection } : rule);
            }
            // If currentSortDirection is none and nextSortDirection is not none, 
            // add clickedField and nextSortDirection to URL sort parameters
            else {
                updatedSortRules = [...sortRules, { field: clickedField, direction: nextSortDirection }];
            }

            // Create updated URL sort parameters string
            const updatedSortParams = updatedSortRules.map(rule => `${rule.field}:${rule.direction}`).join(',');

            // Build final URL and navigate to it
            if (updatedSortRules.length > 0) {
                searchParams.set('sort', updatedSortParams);
            }
            else {
                searchParams.delete('sort');
            }

            const queryString = searchParams.toString();
            
            const newURL = queryString ? `${window.location.pathname}?${queryString}` : window.location.pathname;

            window.location.href = newURL;
        });
    });

});
