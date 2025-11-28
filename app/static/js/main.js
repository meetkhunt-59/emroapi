document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const dropZone = document.getElementById('drop-zone');
    const fileUpload = document.getElementById('file-upload');
    const fileName = document.getElementById('file-name');
    const fileInfo = document.getElementById('file-info');
    const uploadBtn = document.getElementById('upload-btn');
    const progress = document.getElementById('progress');
    const progressFill = document.querySelector('.progress-fill');
    const errorMessage = document.getElementById('error-message');

    // Navigation handling
    const navLinks = document.querySelectorAll('.nav-links a, .cta-button, .footer-section a[href^="#"]');
    let currentFile = null;

    // Drag and drop handlers
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults (e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight() {
        dropZone.classList.add('dragover');
    }

    function unhighlight() {
        dropZone.classList.remove('dragover');
    }

    // Handle dropped files
    dropZone.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // Handle selected files
    fileUpload.addEventListener('change', function() {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length > 0) {
            currentFile = files[0];
            fileName.textContent = currentFile.name;
            fileInfo.classList.remove('hidden');
            errorMessage.classList.add('hidden');
        }
    }

    // Handle upload
    uploadBtn.addEventListener('click', async () => {
        const file = currentFile || fileUpload.files[0];
        if (!file) {
            errorMessage.classList.remove('hidden');
            errorMessage.textContent = 'Please select a file first';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        fileInfo.classList.add('hidden');
        progress.classList.remove('hidden');
        errorMessage.classList.add('hidden');
            progressFill.style.width = '0%';
            progressFill.classList.remove('active');
            
            // Add smooth progress animation
            setTimeout(() => {
                progressFill.classList.add('active');
            }, 100);

            try {
                const response = await fetch('/proxy/9000/upload', {
                    method: 'POST',
                    body: formData
                });            if (!response.ok) {
                throw new Error(await response.text());
            }

            const data = await response.json();
            progressFill.style.width = '100%';
            
            // Redirect to progress page
            window.location.href = `/progress/${data.job_id}`;
        } catch (error) {
            progress.classList.add('hidden');
            fileInfo.classList.remove('hidden');
            errorMessage.classList.remove('hidden');
            errorMessage.textContent = 'Error uploading file: ' + error.message;
        }
    });
});