document.addEventListener('DOMContentLoaded', () => {
    const checkStatusBtn = document.getElementById('check-status');
    const statusText = document.getElementById('status-text');
    const statusIcon = document.querySelector('.status-icon');
    const downloadSection = document.getElementById('download-section');
    const downloadLink = document.getElementById('download-link');
    const errorMessage = document.getElementById('error-message');
    const cooldownSpan = document.getElementById('cooldown');

    let cooldownTime = 0;
    const cooldownInterval = 10; // seconds

    async function checkStatus() {
        const jobId = checkStatusBtn.dataset.jobId;
        
        try {
            const response = await fetch(`/status/${jobId}`);
            if (!response.ok) {
                throw new Error(await response.text());
            }

            const data = await response.json();
            updateStatus(data);
        } catch (error) {
            errorMessage.classList.remove('hidden');
            errorMessage.textContent = 'Error checking status: ' + error.message;
        }
    }

    function updateStatus(data) {
        statusText.textContent = `Status: ${data.status}`;
        
        if (data.status === 'completed') {
            statusIcon.classList.remove('processing');
            statusIcon.classList.add('success');
            downloadSection.classList.remove('hidden');
            downloadLink.href = data.download;
            checkStatusBtn.style.display = 'none';
        } else if (data.status === 'failed') {
            statusIcon.classList.remove('processing');
            errorMessage.classList.remove('hidden');
            errorMessage.textContent = `Error: ${data.error}`;
            checkStatusBtn.style.display = 'none';
        }
    }

    function startCooldown() {
        cooldownTime = cooldownInterval;
        checkStatusBtn.disabled = true;
        cooldownSpan.classList.remove('hidden');
        
        const timer = setInterval(() => {
            cooldownTime--;
            cooldownSpan.textContent = `(${cooldownTime}s)`;
            
            if (cooldownTime <= 0) {
                clearInterval(timer);
                checkStatusBtn.disabled = false;
                cooldownSpan.classList.add('hidden');
            }
        }, 1000);
    }

    checkStatusBtn.addEventListener('click', async () => {
        await checkStatus();
        startCooldown();
    });

    // Initial status check
    checkStatus();
});