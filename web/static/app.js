// Planning Agent RL Feedback Dashboard

const API_BASE = window.location.origin;
let refreshInterval = null;

// Show toast notification
function showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = isError ? 'toast visible error' : 'toast visible';
    setTimeout(() => toast.classList.remove('visible'), 3000);
}

// Format time ago
function timeAgo(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

// Submit rating
async function submitRating(executionId, rating) {
    try {
        const response = await fetch(`${API_BASE}/api/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                execution_id: executionId,
                rating: rating
            })
        });

        if (!response.ok) throw new Error('Failed to submit rating');

        const result = await response.json();
        showToast(`Rating submitted: ${rating} star${rating > 1 ? 's' : ''}`);

        // Refresh data
        loadExecutions();
        loadMetrics();
    } catch (error) {
        showToast('Failed to submit rating', true);
        console.error(error);
    }
}

// Create rating UI for an execution
function createRatingUI(execution) {
    const container = document.createElement('div');

    if (execution.user_rating) {
        // Already rated
        const stars = '★'.repeat(execution.user_rating) + '☆'.repeat(5 - execution.user_rating);
        container.innerHTML = `<span class="rated">${stars}</span>`;
        return container;
    }

    // Thumbs up/down buttons
    const thumbsDiv = document.createElement('div');
    thumbsDiv.className = 'rating-buttons';

    const thumbUp = document.createElement('button');
    thumbUp.className = 'btn btn-thumbs up';
    thumbUp.textContent = '👍';
    thumbUp.title = 'Good (5 stars)';
    thumbUp.onclick = () => submitRating(execution.id, 5);

    const thumbDown = document.createElement('button');
    thumbDown.className = 'btn btn-thumbs down';
    thumbDown.textContent = '👎';
    thumbDown.title = 'Bad (1 star)';
    thumbDown.onclick = () => submitRating(execution.id, 1);

    const expandBtn = document.createElement('button');
    expandBtn.className = 'btn btn-expand';
    expandBtn.textContent = '1-5';
    expandBtn.title = 'Show 5-star rating';

    thumbsDiv.appendChild(thumbUp);
    thumbsDiv.appendChild(thumbDown);
    thumbsDiv.appendChild(expandBtn);
    container.appendChild(thumbsDiv);

    // Star rating (hidden by default)
    const starDiv = document.createElement('div');
    starDiv.className = 'star-rating';

    for (let i = 1; i <= 5; i++) {
        const star = document.createElement('span');
        star.className = 'star';
        star.textContent = '☆';
        star.dataset.rating = i;

        star.onmouseenter = () => {
            starDiv.querySelectorAll('.star').forEach((s, idx) => {
                s.textContent = idx < i ? '★' : '☆';
                s.classList.toggle('active', idx < i);
            });
        };

        star.onmouseleave = () => {
            starDiv.querySelectorAll('.star').forEach(s => {
                s.textContent = '☆';
                s.classList.remove('active');
            });
        };

        star.onclick = () => submitRating(execution.id, i);
        starDiv.appendChild(star);
    }

    expandBtn.onclick = () => {
        starDiv.classList.toggle('visible');
        expandBtn.textContent = starDiv.classList.contains('visible') ? 'Hide' : '1-5';
    };

    container.appendChild(starDiv);
    return container;
}

// Load recent executions
async function loadExecutions() {
    try {
        const response = await fetch(`${API_BASE}/api/executions?limit=20`);
        if (!response.ok) throw new Error('Failed to load executions');

        const result = await response.json();
        const tbody = document.getElementById('executions-body');

        if (!result.data || result.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No executions yet. Start using the agent!</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        result.data.forEach(exec => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${exec.id}</td>
                <td><span class="tool-name">${exec.tool_name}</span></td>
                <td class="${exec.success ? 'success' : 'failure'}">${exec.success ? '✓ Success' : '✗ Failed'}</td>
                <td>${exec.execution_time_ms ? exec.execution_time_ms.toFixed(1) + 'ms' : '-'}</td>
                <td class="time-ago">${timeAgo(exec.created_at)}</td>
                <td></td>
            `;
            tr.lastElementChild.appendChild(createRatingUI(exec));
            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error('Failed to load executions:', error);
    }
}

// Load metrics
async function loadMetrics() {
    try {
        const response = await fetch(`${API_BASE}/api/metrics`);
        if (!response.ok) throw new Error('Failed to load metrics');

        const result = await response.json();
        const data = result.data;

        // Update stats
        document.getElementById('total-executions').textContent = data.summary.total_executions;
        document.getElementById('success-rate').textContent =
            (data.summary.avg_success_rate * 100).toFixed(0) + '%';
        document.getElementById('active-tools').textContent = data.summary.active_tools;
        document.getElementById('rl-status').textContent = data.summary.rl_enabled ? 'Active' : 'Off';

        // Update tool performance table
        const tbody = document.getElementById('metrics-body');

        if (!data.tool_performance || data.tool_performance.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No metrics yet</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        data.tool_performance.forEach(tool => {
            const tr = document.createElement('tr');
            const avgRating = tool.avg_user_rating
                ? '★'.repeat(Math.round(tool.avg_user_rating)) + ` (${tool.avg_user_rating.toFixed(1)})`
                : '-';
            tr.innerHTML = `
                <td><span class="tool-name">${tool.tool_name}</span></td>
                <td>${tool.total_calls}</td>
                <td class="${tool.success_rate >= 0.8 ? 'success' : tool.success_rate >= 0.5 ? '' : 'failure'}">
                    ${(tool.success_rate * 100).toFixed(0)}%
                </td>
                <td>${tool.avg_execution_time_ms ? tool.avg_execution_time_ms.toFixed(1) + 'ms' : '-'}</td>
                <td>${avgRating}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error('Failed to load metrics:', error);
    }
}

// Initialize
function init() {
    loadExecutions();
    loadMetrics();

    // Auto-refresh every 5 seconds
    refreshInterval = setInterval(() => {
        loadExecutions();
        loadMetrics();
    }, 5000);
}

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', init);
