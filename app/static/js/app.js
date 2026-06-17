/**
 * EmroAPI - Main Application Handler
 * Handles file uploads and conversion
 */

let selectedFile = null;

/**
 * Handle file selection from input or drag & drop
 */
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'text/xml', 'text/plain'];
    if (!validTypes.includes(file.type) && !file.name.endsWith('.svg')) {
        showError('Please select a valid image file (PNG, JPG, SVG)');
        return;
    }

    // Validate file size (20MB)
    if (file.size > 20 * 1024 * 1024) {
        showError('File size exceeds 20MB limit');
        return;
    }

    selectedFile = file;
    hideMessages();

    // Show preview section
    document.getElementById('previewSection').style.display = 'block';
    document.getElementById('uploadSection').style.display = 'none';

    // Update file info
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatBytes(file.size);

    // Show preview
    const reader = new FileReader();
    reader.onload = function(e) {
        const previewHtml = `<img src="${e.target.result}" alt="Preview" style="max-width: 100%; border-radius: 8px;">`;
        document.getElementById('originalPreview').innerHTML = previewHtml;
    };
    reader.readAsDataURL(file);

    // Scroll to preview
    setTimeout(() => {
        document.getElementById('previewSection').scrollIntoView({ behavior: 'smooth' });
    }, 100);
}

/**
 * Convert image to DST format
 */
async function convertImage() {
    if (!selectedFile) {
        showError('Please select a file first');
        return;
    }

    const convertBtn = document.getElementById('convertBtn');
    const loading = document.getElementById('loading');

    convertBtn.disabled = true;
    loading.style.display = 'block';
    hideMessages();

    const formData = new FormData();
    formData.append('file', selectedFile);

    // Get dimensions if specified
    const widthInput = document.getElementById('width');
    const heightInput = document.getElementById('height');
    if (widthInput && widthInput.value) {
        formData.append('width', widthInput.value);
    }
    if (heightInput && heightInput.value) {
        formData.append('height', heightInput.value);
    }

    try {
        // Upload file to backend
        const response = await fetch('/proxy/9000/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            let errorMessage;
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorJson.message || 'Upload failed';
            } catch {
                errorMessage = errorText || 'Upload failed';
            }
            throw new Error(errorMessage);
        }

        const data = await response.json();
        const jobId = data.job_id;

        loading.style.display = 'none';
        showSuccess('File uploaded successfully! Processing your image...');

        // Redirect to progress page
        setTimeout(() => {
            window.location.href = `/progress/${jobId}`;
        }, 2000);

    } catch (error) {
        console.error('Error:', error);
        loading.style.display = 'none';
        convertBtn.disabled = false;
        showError('Error uploading file: ' + error.message);
    }
}

/**
 * Initialize app when DOM is ready
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('EmroAPI App Initialized');

    // Add keyboard shortcut for file selection
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'u') {
            e.preventDefault();
            document.getElementById('fileInput').click();
        }
    });

    // Handle paste event for image upload
    document.addEventListener('paste', (e) => {
        const items = e.clipboardData.items;
        for (let item of items) {
            if (item.type.indexOf('image') !== -1) {
                const file = item.getAsFile();
                const fileInput = document.getElementById('fileInput');
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                fileInput.files = dataTransfer.files;
                handleFileSelect({ target: fileInput });
                e.preventDefault();
            }
        }
    });
});
