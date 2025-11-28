document.addEventListener('DOMContentLoaded', () => {
    const checkStatusBtn = document.getElementById('check-status');
    const statusText = document.getElementById('status-text');
    const statusIcon = document.getElementById('statusIcon');
    const statusBadge = document.getElementById('statusBadge');
    const lastUpdated = document.getElementById('lastUpdated');

    const downloadSection = document.getElementById('downloadSection');
    const downloadLink = document.getElementById('download-link');

    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('error-message');

    const actionButtons = document.getElementById('actionButtons');
    const cooldownText = document.getElementById('cooldown');

    const step2Icon = document.querySelector('#step2 .step-icon');
    const step3Icon = document.querySelector('#step3 .step-icon');

    let cooldownTime = 0;
    const cooldownInterval = 10; // seconds

    function updateTimeStamp() {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        lastUpdated.textContent = `${hours}:${minutes}:${seconds}`;
    }

    async function checkStatus() {
        const jobId = checkStatusBtn.dataset.jobId;

        try {
            console.log(`Checking status for job: ${jobId}`);
            const response = await fetch(`/status/${jobId}`);
            console.log(`Status response: ${response.status}`);

            if (!response.ok) {
                throw new Error(await response.text());
            }

            const data = await response.json();
            console.log('Status data:', data);
            updateStatus(data);
        } catch (error) {
            console.error('Status check error:', error);
            showError('Error checking status: ' + error.message);
        }
    }

    function updateStatus(data) {
        updateTimeStamp();

        // Update status badge
        statusBadge.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);
        statusBadge.className = `status-badge ${data.status}`;

        // Update status text
        const statusMessages = {
            'queued': 'Your file is queued for processing. Please wait...',
            'processing': 'Your file is being processed. This usually takes a few seconds...',
            'completed': 'Your file has been successfully processed!',
            'failed': 'There was an error processing your file.'
        };
        statusText.textContent = statusMessages[data.status] || `Status: ${data.status}`;

        console.log(`Status updated to: ${data.status}`);

        if (data.status === 'completed') {
            completeProcessing(data);
        } else if (data.status === 'failed') {
            failProcessing(data);
        } else if (data.status === 'processing' || data.status === 'queued') {
            updateProcessingSteps(data.status);
        }
    }

    function completeProcessing(data) {
        // Update status icon
        statusIcon.className = 'status-icon completed';
        statusIcon.textContent = '✓';

        // Update steps
        step2Icon.className = 'step-icon completed';
        step2Icon.innerHTML = '✓';

        step3Icon.className = 'step-icon completed';
        step3Icon.innerHTML = '✓';

        const step3Line = document.querySelector('#step3').previousElementSibling;
        if (step3Line) step3Line.style.background = '#16a34a';

        // Show download section
        downloadSection.classList.remove('hidden');
        downloadLink.href = data.download || '#';

        // Hide action buttons
        actionButtons.classList.add('hidden');
    }

    function failProcessing(data) {
        // Update status icon
        statusIcon.className = 'status-icon failed';
        statusIcon.textContent = '✗';

        // Update steps
        step2Icon.className = 'step-icon failed';
        step2Icon.innerHTML = '✗';

        // Show error section
        errorSection.classList.remove('hidden');
        errorMessage.textContent = data.error || 'Unknown error occurred';

        // Hide other sections
        downloadSection.classList.add('hidden');
        actionButtons.classList.add('hidden');
    }

    function updateProcessingSteps(status) {
        // Keep step 2 active or queued
        if (status === 'queued') {
            step2Icon.className = 'step-icon pending';
            step2Icon.innerHTML = '●';
        } else {
            step2Icon.className = 'step-icon active';
            step2Icon.innerHTML = '<div class="spinner"></div>';
        }

        // Ensure step 3 is pending
        step3Icon.className = 'step-icon pending';
        step3Icon.innerHTML = '●';
    }

    function showError(message) {
        errorSection.classList.remove('hidden');
        errorMessage.textContent = message;
        actionButtons.classList.add('hidden');
    }

    function startCooldown() {
        cooldownTime = cooldownInterval;
        checkStatusBtn.disabled = true;
        cooldownText.classList.remove('hidden');

        const timer = setInterval(() => {
            cooldownTime--;
            cooldownText.textContent = `(${cooldownTime}s)`;

            if (cooldownTime <= 0) {
                clearInterval(timer);
                checkStatusBtn.disabled = false;
                cooldownText.classList.add('hidden');
            }
        }, 1000);
    }

    checkStatusBtn.addEventListener('click', async () => {
        await checkStatus();
        startCooldown();
    });

    // Initial status check
    checkStatus();

    // Auto-check every 10 seconds if not completed/failed
    setInterval(() => {
        if (!downloadSection.classList.contains('hidden') || !errorSection.classList.contains('hidden')) {
            return; // Stop checking if already completed or failed
        }
        checkStatus();
    }, 10000);
});
