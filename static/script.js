document.addEventListener('DOMContentLoaded', () => {
    console.log("[DEBUG] DOM content fully loaded.");

    /**
     * Generic function to handle navigation buttons
     * @param {string} buttonId - ID of the button
     * @param {string} targetUrl - URL to navigate to
     */
    function setupNavigation(buttonId, targetUrl) {
        const button = document.getElementById(buttonId);
        if (button) {
            button.addEventListener('click', () => {
                console.log(`[DEBUG] ${buttonId} clicked. Navigating to ${targetUrl}.`);
                window.location.href = targetUrl;
            });
        } else {
            console.error(`[DEBUG] Navigation button ${buttonId} not found.`);
        }
    }

    // Set up navigation buttons
    setupNavigation('back_options-btn', '/options');
    setupNavigation('home-btn', '/');
    setupNavigation('next-btn', '/options');
    setupNavigation('back_index-btn', '/');
    setupNavigation('specific_search_btn', '/specific_search');

    /**
     * Function to handle Quick Search Form Submission
     */
    const quickSearchForm = document.getElementById('quick-search-form');
    const resultsList = document.getElementById('results-list');

    if (quickSearchForm && resultsList) {
        quickSearchForm.addEventListener('submit', async (e) => {
            e.preventDefault(); // Prevent form reload

            const keyword = document.getElementById('keyword').value.trim();
            if (!keyword) {
                alert('Please enter a keyword.');
                return;
            }

            resultsList.innerHTML = ''; // Clear previous results
            console.log(`[DEBUG] Performing quick search for keyword: "${keyword}"`);

            try {
                const formData = new FormData();
                formData.append('keyword', keyword);

                const response = await fetch('/quick_search', {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }

                const data = await response.json();
                console.log('[DEBUG] Quick search response:', data);

                // Display results
                if (data.results && data.results.length > 0) {
                    data.results.forEach(result => {
                        const li = document.createElement('li');
                        li.textContent = `File: ${result.file}, Page: ${result.page}, Context: ${result.context}`;
                        resultsList.appendChild(li);
                    });
                } else {
                    resultsList.innerHTML = '<li>No matches found.</li>';
                }
            } catch (error) {
                console.error('[DEBUG] Error fetching quick search results:', error);
                resultsList.innerHTML = '<li>An error occurred while searching. Please try again later.</li>';
            }
        });
    } else {
        console.error('[DEBUG] Quick search form or results list not found.');
    }

    /**
     * Function to handle file uploads
     * @param {string} buttonId - ID of the upload button
     * @param {string} fileInputId - ID of the file input
     * @param {string} progressTextId - ID of the progress text element
     * @param {string} endpoint - API endpoint to send files to
     * @param {boolean} isExcel - Set to true for single Excel/CSV file uploads
     */
    function handleUpload(buttonId, fileInputId, progressTextId, endpoint, isExcel = false) {
        const uploadButton = document.getElementById(buttonId);
        const fileInput = document.getElementById(fileInputId);
        const progressText = document.getElementById(progressTextId);

        if (!uploadButton || !fileInput || !progressText) {
            console.error("[DEBUG] Missing elements for upload:", { buttonId, fileInputId, progressTextId });
            return;
        }

        uploadButton.addEventListener('click', async (e) => {
            e.preventDefault(); // Prevent default behavior
            console.log(`[DEBUG] ${buttonId} clicked.`);

            if (!fileInput.files || fileInput.files.length === 0) {
                progressText.textContent = "Please select a file to upload.";
                return;
            }

            progressText.textContent = "Uploading file...";
            const formData = new FormData();

            if (isExcel) {
                formData.append('file', fileInput.files[0]); // For single Excel/CSV file
            } else {
                for (const file of fileInput.files) {
                    formData.append('files', file); // For multiple PDFs
                }
            }

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }

                const data = await response.json();
                console.log(`[DEBUG] Upload response from ${endpoint}:`, data);
                progressText.textContent = data.message || "Upload successful!";
            } catch (error) {
                console.error(`[DEBUG] Upload error for ${endpoint}:`, error);
                progressText.textContent = "An error occurred during upload.";
            }
        });
    }

    // Set up upload functionality for PDFs
    handleUpload(
        'pdf-upload-btn',        // Button ID
        'files',                 // File input ID
        'progress-text',         // Progress text ID
        '/uploaded_pdfs',        // Endpoint for PDF uploads
        false                    // Not an Excel upload
    );

    // Set up upload functionality for Excel/CSV files
    handleUpload(
        'excel-upload-btn',      // Button ID
        'excel-files',           // File input ID
        'excel-progress-text',   // Progress text ID
        '/uploaded_keywords',    // Endpoint for Excel/CSV uploads
        true                     // Mark as Excel upload for single file handling
    );

    // Search Button Functionality
    const standardSearchButton = document.getElementById('standard_search_btn');
    if (standardSearchButton) {
        standardSearchButton.addEventListener('click', function () {
            console.log("[DEBUG] Search button clicked.");

            const progressBar = document.getElementById('progress-bar');
            const progressText = document.getElementById('progress-text');

            if (!progressBar || !progressText) {
                console.error("[DEBUG] Progress elements missing in DOM.");
                return;
            }

            progressBar.value = 0;
            progressText.textContent = "Starting search...";

            // Send search request
            fetch('/search', { method: 'POST' })
                .then(response => {
                    console.log("[DEBUG] Search request sent.");
                    return response.json();
                })
                .then(data => {
                    console.log("[DEBUG] Search response:", data);
                    if (data.results && data.results.length > 0) {
                        progressText.textContent = "Search completed!";
                    } else {
                        progressText.textContent = "No files to process.";
                    }
                })
                .catch(error => {
                    console.error("[DEBUG] Search error:", error);
                    progressText.textContent = "An error occurred during search.";
                });
        });
    }
});
