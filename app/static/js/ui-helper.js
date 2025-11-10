/**
 * UI Helper - Handles UI interactions and animations
 */

// Mobile Menu Toggle
function toggleMobileMenu() {
    const mobileNav = document.getElementById('mobileNav');
    const mobileOverlay = document.getElementById('mobileOverlay');
    mobileNav.classList.toggle('active');
    mobileOverlay.classList.toggle('active');
}

// Scroll observer for animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('animated');
        }
    });
}, observerOptions);

document.querySelectorAll('.animate-on-scroll').forEach(el => {
    observer.observe(el);
});

// Navbar scroll effect
window.addEventListener('scroll', () => {
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 50) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
});

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

// Drag and drop for upload section
const uploadSection = document.getElementById('uploadSection');

if (uploadSection) {
    uploadSection.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadSection.style.borderColor = 'var(--secondary)';
        uploadSection.style.background = '#DCFCE7';
    });

    uploadSection.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadSection.style.borderColor = 'var(--primary)';
        uploadSection.style.background = '#F0FDF4';
    });

    uploadSection.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadSection.style.borderColor = 'var(--primary)';
        uploadSection.style.background = '#F0FDF4';

        const file = e.dataTransfer.files[0];
        if (file && (file.type.startsWith('image/') || file.name.endsWith('.svg'))) {
            const fileInput = document.getElementById('fileInput');
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            fileInput.files = dataTransfer.files;
            handleFileSelect({ target: fileInput });
        }
    });
}

/**
 * Format bytes to human readable format
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Show error message
 */
function showError(message) {
    const errorMessage = document.getElementById('errorMessage');
    if (errorMessage) {
        errorMessage.textContent = message;
        errorMessage.classList.add('show');
        setTimeout(() => {
            errorMessage.classList.remove('show');
        }, 5000);
    }
}

/**
 * Show success message
 */
function showSuccess(message) {
    const successMessage = document.getElementById('successMessage');
    if (successMessage) {
        successMessage.textContent = message;
        successMessage.classList.add('show');
        setTimeout(() => {
            successMessage.classList.remove('show');
        }, 5000);
    }
}

/**
 * Hide all messages
 */
function hideMessages() {
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');
    if (errorMessage) errorMessage.classList.remove('show');
    if (successMessage) successMessage.classList.remove('show');
}
