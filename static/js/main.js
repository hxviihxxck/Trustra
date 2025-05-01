// Toast notification system
function showToast(message, type = 'info', duration = 3000) {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'fixed bottom-4 right-4 z-50 flex flex-col space-y-2';
        document.body.appendChild(toastContainer);
    }
    
    // Determine toast color based on type
    let bgColor, textColor, borderColor;
    switch (type) {
        case 'success':
            bgColor = 'bg-green-50 dark:bg-green-900';
            textColor = 'text-green-800 dark:text-green-100';
            borderColor = 'border-green-500';
            icon = '<i class="fas fa-check-circle text-green-500"></i>';
            break;
        case 'error':
            bgColor = 'bg-red-50 dark:bg-red-900';
            textColor = 'text-red-800 dark:text-red-100';
            borderColor = 'border-red-500';
            icon = '<i class="fas fa-times-circle text-red-500"></i>';
            break;
        case 'warning':
            bgColor = 'bg-yellow-50 dark:bg-yellow-900';
            textColor = 'text-yellow-800 dark:text-yellow-100';
            borderColor = 'border-yellow-500';
            icon = '<i class="fas fa-exclamation-triangle text-yellow-500"></i>';
            break;
        default: // info
            bgColor = 'bg-blue-50 dark:bg-blue-900';
            textColor = 'text-blue-800 dark:text-blue-100';
            borderColor = 'border-blue-500';
            icon = '<i class="fas fa-info-circle text-blue-500"></i>';
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `flex items-center p-3 rounded-lg shadow-md ${bgColor} ${textColor} border-l-4 ${borderColor} transform transition-all duration-300 ease-in-out translate-x-full opacity-0`;
    toast.innerHTML = `
        <div class="flex-shrink-0 mr-3">
            ${icon}
        </div>
        <div class="flex-grow">${message}</div>
        <button class="ml-4 focus:outline-none">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // Add to container
    toastContainer.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.classList.remove('translate-x-full', 'opacity-0');
    }, 10);
    
    // Set up dismiss button
    toast.querySelector('button').addEventListener('click', () => {
        dismissToast(toast);
    });
    
    // Auto dismiss after duration
    setTimeout(() => {
        dismissToast(toast);
    }, duration);
}

function dismissToast(toast) {
    toast.classList.add('translate-x-full', 'opacity-0');
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 300);
}

// Global error handler for fetch
window.addEventListener('unhandledrejection', function(event) {
    if (event.reason && event.reason.message) {
        showToast(`Error: ${event.reason.message}`, 'error');
    } else {
        showToast('An unexpected error occurred', 'error');
    }
});

// Init function that runs when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize dark mode from localStorage
    const darkModeEnabled = localStorage.getItem('darkMode') === 'true';
    if (darkModeEnabled) {
        document.documentElement.classList.add('dark');
    }
    
    // Add smooth transition to body
    document.body.classList.add('transition-colors', 'duration-200');
});
