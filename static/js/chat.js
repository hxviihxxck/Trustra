document.addEventListener('alpine:init', () => {
    // Define Alpine.js data and methods for the chat widget
    window.formatTimestamp = function(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    window.sendMessage = function() {
        if (!this.currentMessage.trim()) return;
        
        // Add user message to chat
        this.messages.push({
            sender: 'user',
            content: this.currentMessage,
            timestamp: new Date().toISOString()
        });
        
        const userMessage = this.currentMessage;
        this.currentMessage = '';
        
        // Scroll to bottom
        this.$nextTick(() => {
            const chatMessages = document.getElementById('chat-messages');
            if (chatMessages) {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        });
        
        // Simulate typing indicator
        this.messages.push({
            sender: 'system',
            content: '...',
            timestamp: new Date().toISOString(),
            isTyping: true
        });
        
        // Process the message on the backend
        fetch('/chat/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                message: userMessage,
                userEmail: this.userEmail,
                userName: this.userName
            })
        })
        .then(response => response.json())
        .then(data => {
            // Remove typing indicator
            this.messages = this.messages.filter(msg => !msg.isTyping);
            
            // Add response message
            this.messages.push({
                sender: 'system',
                content: data.response,
                timestamp: new Date().toISOString()
            });
            
            // Scroll to bottom again
            this.$nextTick(() => {
                const chatMessages = document.getElementById('chat-messages');
                if (chatMessages) {
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }
            });
        })
        .catch(error => {
            console.error('Error sending message:', error);
            // Remove typing indicator
            this.messages = this.messages.filter(msg => !msg.isTyping);
            
            // Add error message
            this.messages.push({
                sender: 'system',
                content: 'Sorry, there was an error processing your message. Please try again.',
                timestamp: new Date().toISOString()
            });
        });
    }
    
    // Helper function to get CSRF token
    function getCsrfToken() {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        return csrfToken || '';
    }
});

// Fallback responses when backend is not available or in development
const fallbackResponses = [
    "I'd be happy to help with that! Could you provide more details?",
    "That's a great question. Let me check that for you.",
    "I understand your concern. Here's what I can suggest...",
    "Thanks for reaching out. Let me guide you through this.",
    "I'm looking into this for you. Just a moment please.",
    "We value your feedback. I'll make sure this gets addressed.",
    "Have you tried checking the Trustra documentation? It might have the answer you're looking for.",
    "I'll connect you with a specialist who can help with that specific issue.",
    "Let me know if you need any clarification on anything I've explained.",
    "Is there anything else you'd like help with today?"
];

// If no backend response (for initial development), use this to simulate
function getSimulatedResponse(userMessage) {
    // Check for specific keyword matches
    if (userMessage.toLowerCase().includes('password')) {
        return "Trustra keeps your passwords secure with end-to-end encryption. Nobody can access your passwords except you.";
    }
    if (userMessage.toLowerCase().includes('subscription') || userMessage.toLowerCase().includes('premium')) {
        return "Premium subscriptions start at $4.99/month and include features like password health checks, breach monitoring, and emergency access.";
    }
    if (userMessage.toLowerCase().includes('refund') || userMessage.toLowerCase().includes('cancel')) {
        return "You can cancel your subscription anytime from your account settings. Refunds are processed according to our refund policy within 14 days of purchase.";
    }
    
    // Otherwise, return a random response
    return fallbackResponses[Math.floor(Math.random() * fallbackResponses.length)];
}