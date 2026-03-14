// Dashboard JavaScript - Modern Professional Design

// Store chart instances globally to prevent canvas reuse errors
let chartInstances = {
    lineChart: null,
    pieChart: null,
    barChart: null,
    comparisonChart: null,
    explorerLineChart: null,
    explorerPieChart: null,
    explorerBarChart: null,
    explorerComparisonChart: null
};

// All available components
const ALL_COMPONENTS = [
    'AdminCenter', 'App Client', 'Async Scheduling (Persistent Executor, CommonJ)',
    'Batch', 'Bean Validation', 'Build', 'CDI', 'Classloading',
    'Cloud/Virtualization', 'Core Security', 'Database (jdbc, oracle, db2, derby)',
    'Docs', 'Dynacache', 'EE / MP Concurrency', 'EJB Container', 'IIOP/ORB',
    'IBM i', 'Install', 'InstantOn', 'Intelligent Management', 'JAX-RS',
    'Jakarta Data', 'Java EE Platform', 'JCA', 'JPA', 'JSON',
    'Kernel/Bootstrap', 'MCP', 'Messaging', 'MicroProfile Core (config, fault tolerance, reactive)',
    'MicroProfile GraphQL', 'MicroProfile Observability (metrics, open tracing, health)',
    'MicroProfile Open API', 'MicroProfile REST Client', 'Mongo', 'OSGi Applications',
    'Observability', 'Real-Time Comm (WebRTC, SIP)', 'Repository', 'Security SSO (jwt, oauth, oidc, social, mpjwt, saml)',
    'Spring Boot', 'Systems Management', 'Transactions', 'Transport (cfw, http, ssl, websockets)',
    'Usage Metering', 'WAS on Cloud', 'Web Comps (servlet, httpsession, jsp, jsf, etc)',
    'Web Services', 'Web Services Security', 'WebSphere Automation', 'z/OS'
];

let selectedComponents = [];

// Animated counter function
function animateCounter(element, target, duration = 1000) {
    const start = 0;
    const increment = target / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = Math.round(target);
            clearInterval(timer);
        } else {
            element.textContent = Math.round(current);
        }
    }, 16);
}

// Load dashboard data from Flask API
async function loadDashboardData() {
    try {
        const response = await fetch('/api/dashboard/data');
        const data = await response.json();

        if (!data || !data.summary) {
            document.body.innerHTML = '<div class="loading"><div class="loading-spinner"></div><div><h2>No Data Available</h2><p style="margin-top:10px;color:#8899a6;">Dashboard data will be available after the first defect check.</p></div></div>';
            return;
        }

        renderDashboard(data);
    } catch (error) {
        console.error('Error loading dashboard data:', error);
        document.body.innerHTML = '<div class="loading"><div class="loading-spinner"></div><div><h2>Error Loading Data</h2><p style="margin-top:10px;color:#8899a6;">Please try refreshing the page.</p></div></div>';
    }
}

function renderDashboard(data) {
    // Set header info with safety checks
    if (data.weekStart && data.weekEnd) {
        document.getElementById('weekRange').textContent = `${data.weekStart} → ${data.weekEnd}`;
    } else {
        // Fallback if weekStart/weekEnd are missing
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('weekRange').textContent = `Week ending ${today}`;
    }

    // Render KPI cards with icons
    renderKPICards(data.summary);

    // Render charts
    renderLineChart(data.dailyTrend);
    renderPieChart(data.componentBreakdown, data.summary);
    renderBarChart(data.componentBreakdown);
    
    // Render week vs week comparison chart
    renderWeekComparisonChart(data);

    // Render recent defects table
    renderRecentDefects(data);
}

function renderKPICards(summary) {
    const kpiRow = document.getElementById('kpiRow');
    const trendClass = summary.trendPercentage < 0 ? 'positive' : summary.trendPercentage > 0 ? 'negative' : 'neutral';
    const trendIcon = summary.trendPercentage < 0 ? '↓' : summary.trendPercentage > 0 ? '↑' : '→';
    
    const untriagedPercent = summary.totalDefects > 0
        ? Math.round((summary.untriaged / summary.totalDefects) * 100)
        : 0;

    const slaCompliance = Math.max(0, Math.min(100, 100 - untriagedPercent));

    kpiRow.innerHTML = `
        <div class="kpi-card" style="animation-delay: 0s;">
            <div class="icon">🏆</div>
            <div class="label">Total Defects</div>
            <div class="value" data-target="${summary.totalDefects}">0</div>
            <div class="change ${trendClass}">
                <span>${trendIcon}</span> ${Math.abs(summary.trendPercentage)}% from last week
            </div>
        </div>
        <div class="kpi-card" style="animation-delay: 0.1s;">
            <div class="icon">📍</div>
            <div class="label">Untriaged</div>
            <div class="value" data-target="${summary.untriaged}">0</div>
            <div class="change neutral">
                ${untriagedPercent}% of total
            </div>
        </div>
        <div class="kpi-card" style="animation-delay: 0.2s;">
            <div class="icon">⭐</div>
            <div class="label">Test Bugs</div>
            <div class="value" data-target="${summary.testBugs}">0</div>
            <div class="change ${summary.testBugs > 50 ? 'negative' : 'neutral'}">
                <span>●</span> ${summary.testBugs > 50 ? '8%' : '0%'} from last week
            </div>
        </div>
        <div class="kpi-card" style="animation-delay: 0.3s;">
            <div class="icon">🔒</div>
            <div class="label">Product Bugs</div>
            <div class="value" data-target="${summary.productBugs}">0</div>
            <div class="change ${summary.productBugs > 0 ? 'negative' : 'positive'}">
                <span>●</span> Critical
            </div>
        </div>
        <div class="kpi-card" style="animation-delay: 0.4s;">
            <div class="icon">🔮</div>
            <div class="label">Infrastructure Issues</div>
            <div class="value" data-target="${summary.infraBugs}">0</div>
            <div class="change neutral">
                System Issues
            </div>
        </div>
        <div class="kpi-card" style="animation-delay: 0.5s;">
            <div class="label">SLA Compliance</div>
            <div style="position: relative; height: 70px; margin: 6px 0;">
                <svg class="progress-ring" width="70" height="70">
                    <circle
                        stroke="rgba(255,255,255,0.1)"
                        stroke-width="6"
                        fill="transparent"
                        r="30"
                        cx="35"
                        cy="35"
                    />
                    <circle
                        class="progress-ring-circle"
                        stroke="#00d4aa"
                        stroke-width="6"
                        fill="transparent"
                        r="30"
                        cx="35"
                        cy="35"
                        stroke-dasharray="188"
                        stroke-dashoffset="${188 - (188 * slaCompliance) / 100}"
                        stroke-linecap="round"
                    />
                </svg>
                <div class="progress-value">${slaCompliance}%</div>
            </div>
        </div>
    `;
    
    // Animate counters
    setTimeout(() => {
        document.querySelectorAll('.kpi-card .value[data-target]').forEach(el => {
            const target = parseInt(el.getAttribute('data-target'));
            animateCounter(el, target, 1200);
        });
    }, 100);
}

function renderWeekComparisonChart(data) {
    const ctx = document.getElementById('comparisonChart').getContext('2d');
    
    // Destroy existing chart
    if (chartInstances.comparisonChart) {
        chartInstances.comparisonChart.destroy();
    }
    
    // Check if we have last week data
    const hasLastWeekData = data.weekComparison &&
                           data.weekComparison.lastWeek &&
                           data.weekComparison.lastWeek.total > 0;
    
    Chart.defaults.color = '#8899a6';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';
    
    // Build labels with dates for clarity
    let lastWeekLabel = 'Previous';
    if (hasLastWeekData && data.weekComparison.lastWeekDate) {
        const date = new Date(data.weekComparison.lastWeekDate);
        lastWeekLabel = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    
    // If no last week data, show only this week
    const labels = hasLastWeekData ? [lastWeekLabel, 'This Week'] : ['This Week'];
    const totalData = hasLastWeekData
        ? [data.weekComparison.lastWeek.total, data.summary.totalDefects]
        : [data.summary.totalDefects];
    const untriagedData = hasLastWeekData
        ? [data.weekComparison.lastWeek.untriaged, data.summary.untriaged]
        : [data.summary.untriaged];
    
    chartInstances.comparisonChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Total',
                data: totalData,
                backgroundColor: '#1d9bf0',
                borderRadius: 6,
                barThickness: 50
            }, {
                label: 'Untriaged',
                data: untriagedData,
                backgroundColor: '#ff6b9d',
                borderRadius: 6,
                barThickness: 50
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#e1e8ed',
                        font: { size: 11, weight: '600' },
                        padding: 10,
                        usePointStyle: true,
                        boxWidth: 8,
                        boxHeight: 8
                    }
                },
                tooltip: {
                    backgroundColor: '#1a1f3a',
                    titleColor: '#fff',
                    bodyColor: '#e1e8ed',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 10,
                    bodyFont: { size: 11 },
                    titleFont: { size: 11 }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { 
                        color: '#e1e8ed', 
                        font: { size: 11, weight: '600' } 
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false },
                    ticks: { color: '#8899a6', font: { size: 10 } }
                }
            }
        }
    });
}

function renderLineChart(dailyTrend) {
    const ctx = document.getElementById('lineChart').getContext('2d');
    
    // Destroy existing chart
    if (chartInstances.lineChart) {
        chartInstances.lineChart.destroy();
    }
    
    Chart.defaults.color = '#8899a6';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';
    
    chartInstances.lineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dailyTrend.labels,
            datasets: [{
                label: 'Total Defects',
                data: dailyTrend.total,
                borderColor: '#1d9bf0',
                backgroundColor: 'rgba(29, 155, 240, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2,
                pointRadius: 3,
                pointHoverRadius: 5,
                pointBackgroundColor: '#1d9bf0',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }, {
                label: 'Untriaged',
                data: dailyTrend.untriaged,
                borderColor: '#ff6b9d',
                backgroundColor: 'rgba(255, 107, 157, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2,
                pointRadius: 3,
                pointHoverRadius: 5,
                pointBackgroundColor: '#ff6b9d',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#e1e8ed',
                        font: { size: 11, weight: '600' },
                        padding: 8,
                        usePointStyle: true,
                        boxWidth: 8,
                        boxHeight: 8
                    }
                },
                tooltip: {
                    backgroundColor: '#1a1f3a',
                    titleColor: '#fff',
                    bodyColor: '#e1e8ed',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 8,
                    displayColors: true,
                    bodyFont: { size: 10 },
                    titleFont: { size: 10 }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false },
                    ticks: { color: '#8899a6', font: { size: 10 } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false },
                    ticks: { color: '#8899a6', font: { size: 10 }, stepSize: 20 }
                }
            }
        }
    });
}

function renderPieChart(componentBreakdown, summary) {
    const ctx = document.getElementById('pieChart').getContext('2d');
    
    // Destroy existing chart
    if (chartInstances.pieChart) {
        chartInstances.pieChart.destroy();
    }
    
    // Get component data
    const components = componentBreakdown.labels || [];
    const totals = componentBreakdown.total || [];
    
    // Generate colors for each component
    const colors = [
        '#ff6b9d', '#ffad1f', '#1d9bf0', '#00d4aa',
        '#a78bfa', '#fb923c', '#34d399', '#f472b6',
        '#60a5fa', '#fbbf24', '#4ade80', '#c084fc'
    ];
    
    chartInstances.pieChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: components,
            datasets: [{
                data: totals,
                backgroundColor: colors.slice(0, components.length),
                borderWidth: 0,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#e1e8ed',
                        font: { size: 10, weight: '600' },
                        padding: 8,
                        usePointStyle: true,
                        boxWidth: 8,
                        boxHeight: 8
                    }
                },
                tooltip: {
                    backgroundColor: '#1a1f3a',
                    titleColor: '#fff',
                    bodyColor: '#e1e8ed',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 8,
                    bodyFont: { size: 10 },
                    titleFont: { size: 10 },
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        },
        plugins: [{
            beforeDraw: function(chart) {
                const width = chart.width;
                const height = chart.height;
                const ctx = chart.ctx;
                ctx.restore();
                const fontSize = (height / 130).toFixed(2);
                ctx.font = `bold ${fontSize}em sans-serif`;
                ctx.textBaseline = 'middle';
                ctx.fillStyle = '#fff';
                const text = summary.totalDefects.toString();
                const textX = Math.round((width - ctx.measureText(text).width) / 2);
                const textY = height / 2 - 8;
                ctx.fillText(text, textX, textY);
                
                ctx.font = `${fontSize * 0.4}em sans-serif`;
                ctx.fillStyle = '#8899a6';
                const subtext = 'Total';
                const subtextX = Math.round((width - ctx.measureText(subtext).width) / 2);
                ctx.fillText(subtext, subtextX, textY + 18);
                ctx.save();
            }
        }]
    });
}

function renderBarChart(componentBreakdown) {
    const ctx = document.getElementById('barChart').getContext('2d');
    
    // Destroy existing chart
    if (chartInstances.barChart) {
        chartInstances.barChart.destroy();
    }
    
    // Show all components (no limit)
    const components = componentBreakdown.labels || [];
    
    // Check if we have the new detailed breakdown, otherwise use old format
    const hasDetailedBreakdown = componentBreakdown.testBugs && componentBreakdown.testBugs.length > 0;
    
    console.log('=== Bar Chart Debug ===');
    console.log('componentBreakdown:', componentBreakdown);
    console.log('hasDetailedBreakdown:', hasDetailedBreakdown);
    
    let untriaged, testBugs, productBugs, infraBugs;
    
    if (hasDetailedBreakdown) {
        // New format with detailed breakdown
        untriaged = componentBreakdown.untriaged || [];
        testBugs = componentBreakdown.testBugs || [];
        productBugs = componentBreakdown.productBugs || [];
        infraBugs = componentBreakdown.infraBugs || [];
        console.log('Using detailed breakdown:', { untriaged, testBugs, productBugs, infraBugs });
    } else {
        // Old format - show total and untriaged only
        const total = componentBreakdown.total || [];
        untriaged = componentBreakdown.untriaged || [];
        // Calculate triaged as total - untriaged
        testBugs = total.map((t, i) => Math.max(0, t - (untriaged[i] || 0)));
        productBugs = [];
        infraBugs = [];
    }
    
    chartInstances.barChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: components,
            datasets: [{
                label: 'Untriaged',
                data: untriaged,
                backgroundColor: '#ff6b9d',
                borderRadius: 4,
                barThickness: 15
            }, {
                label: 'Test Bugs',
                data: testBugs,
                backgroundColor: '#ffad1f',
                borderRadius: 4,
                barThickness: 15
            }, {
                label: 'Product Bugs',
                data: productBugs,
                backgroundColor: '#1d9bf0',
                borderRadius: 4,
                barThickness: 15
            }, {
                label: 'Infrastructure',
                data: infraBugs,
                backgroundColor: '#00d4aa',
                borderRadius: 4,
                barThickness: 15
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#e1e8ed',
                        font: { size: 10, weight: '600' },
                        padding: 8,
                        usePointStyle: true,
                        boxWidth: 8,
                        boxHeight: 8
                    }
                },
                tooltip: {
                    backgroundColor: '#1a1f3a',
                    titleColor: '#fff',
                    bodyColor: '#e1e8ed',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 8,
                    bodyFont: { size: 10 },
                    titleFont: { size: 10 }
                }
            },
            scales: {
                x: {
                    stacked: true,
                    grid: { display: false },
                    ticks: { color: '#8899a6', font: { size: 9 } }
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false },
                    ticks: { color: '#8899a6', font: { size: 9 } }
                }
            }
        }
    });
}

async function renderRecentDefects(data) {
    const tbody = document.getElementById('defectsTableBody');
    
    try {
        // Fetch SOE Triage defects from Flask API
        const response = await fetch('/api/soe-defects');
        const result = await response.json();
        const allDefects = result.defects || [];
        const lastFetch = result.last_fetch;
        
        // Get monitored components from dashboard data (data.componentBreakdown.labels)
        const monitoredComponentNames = data.componentBreakdown?.labels || [];
        
        console.log('=== My Monitored Components SOE Triage ===');
        console.log('All defects:', allDefects.length);
        console.log('Monitored components from dashboard:', monitoredComponentNames);
        
        // Filter defects by monitored components only (for "My Monitored Components" tab)
        const soeTriageDefects = allDefects.filter(defect => {
            const match = monitoredComponentNames.some(compName => {
                const compLower = compName.toLowerCase().trim();
                const functionalAreaLower = (defect.functionalArea || '').toLowerCase().trim();
                const filedAgainstLower = (defect.filedAgainst || '').toLowerCase().trim();
                
                console.log(`Checking "${compName}" against defect ${defect.id}:`, {
                    functionalArea: defect.functionalArea,
                    filedAgainst: defect.filedAgainst,
                    matchFA: functionalAreaLower === compLower,
                    matchFiled: filedAgainstLower === compLower
                });
                
                // Use exact match instead of partial match
                return functionalAreaLower === compLower || filedAgainstLower === compLower;
            });
            return match;
        });
        
        console.log('Filtered defects for monitored components:', soeTriageDefects.length);
        
        // Show loading state initially
        if (!lastFetch) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; padding: 20px; color: #8899a6;">
                        <div style="display: flex; align-items: center; justify-content: center; gap: 10px;">
                            <div class="loading-spinner" style="width: 20px; height: 20px; border: 2px solid rgba(255,255,255,0.1); border-top-color: #1d9bf0; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                            <span>Fetching SOE Triage defects from Jazz/RTC...</span>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }
        
        if (soeTriageDefects.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; padding: 20px; color: #8899a6;">
                        ✅ No overdue SOE triage defects found
                        <div style="margin-top: 8px; font-size: 11px; opacity: 0.7;">
                            Last checked: ${new Date(lastFetch).toLocaleString('en-IN', {
                                month: 'short',
                                day: 'numeric',
                                hour: 'numeric',
                                minute: '2-digit',
                                hour12: true
                            })}
                        </div>
                    </td>
                </tr>
            `;
        } else {
            tbody.innerHTML = soeTriageDefects.map(defect => `
                <tr>
                    <td>
                        <a href="https://wasrtc.hursley.ibm.com:9443/jazz/web/projects/WS-CD#action=com.ibm.team.workitem.viewWorkItem&id=${defect.id}"
                           target="_blank"
                           class="defect-id"
                           style="color: #1d9bf0; text-decoration: none;">
                            ${defect.id}
                        </a>
                    </td>
                    <td title="${defect.summary}">${defect.summary}</td>
                    <td>${defect.functionalArea}</td>
                    <td>${defect.filedAgainst}</td>
                    <td>${defect.creationDate}</td>
                    <td>${defect.ownedBy}</td>
                </tr>
        `).join('');
        }
    } catch (error) {
        console.error('Error loading SOE defects:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 20px; color: #ff6b9d;">
                    ❌ Error loading SOE Triage defects
                </td>
            </tr>
        `;
    }
}

// No auto-load for monitored components - user selects components first

// Add keyboard shortcut for refresh (R key)
document.addEventListener('keydown', (e) => {
    if (e.key === 'r' || e.key === 'R') {
        console.log('Refreshing dashboard...');
        loadDashboardData();
    }
});

// ============================================
// COMPONENT EXPLORER FUNCTIONALITY
// ============================================

// Initialize component explorer
function initializeComponentExplorer() {
    const componentGrid = document.getElementById('componentGrid');
    
    // Create checkboxes for all components
    componentGrid.innerHTML = ALL_COMPONENTS.map(component => `
        <div class="component-checkbox">
            <input type="checkbox" id="comp-${component.replace(/[^a-zA-Z0-9]/g, '-')}" value="${component}">
            <label for="comp-${component.replace(/[^a-zA-Z0-9]/g, '-')}">${component}</label>
        </div>
    `).join('');
    
    // Add event listeners to checkboxes
    const checkboxes = componentGrid.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateSelectedComponents);
    });
    
    // Fetch Data button
    document.getElementById('fetchDataBtn').addEventListener('click', fetchAllComponentsData);
    
    // Select All button
    document.getElementById('selectAllBtn').addEventListener('click', () => {
        checkboxes.forEach(cb => cb.checked = true);
        updateSelectedComponents();
    });
    
    // Clear All button
    document.getElementById('clearAllBtn').addEventListener('click', () => {
        checkboxes.forEach(cb => cb.checked = false);
        updateSelectedComponents();
    });
    
    // View Dashboard button
    document.getElementById('viewDashboardBtn').addEventListener('click', generateExplorerDashboard);
    
    // Back to Selection button
    document.getElementById('backToSelectionBtn').addEventListener('click', () => {
        // Hide dashboard, show selector
        document.querySelector('.component-explorer').style.display = 'block';
        document.getElementById('explorerDashboard').style.display = 'none';
    });
}

// Fetch all components data from Flask API using check-now endpoint
async function fetchAllComponentsData() {
    const fetchBtn = document.getElementById('fetchDataBtn');
    const originalText = fetchBtn.innerHTML;
    
    // Disable button and show loading
    fetchBtn.disabled = true;
    fetchBtn.innerHTML = '⏳ Fetching data for all 51 components...';
    
    try {
        // Call Flask API to trigger check-now (fetches all components)
        const response = await fetch('/api/check-now', {
            method: 'POST'
        });
        const result = await response.json();
        
        if (result.message && result.message.includes('completed')) {
            fetchBtn.innerHTML = '✅ Data fetched successfully!';
            setTimeout(() => {
                fetchBtn.innerHTML = originalText;
                fetchBtn.disabled = false;
            }, 2000);
        } else {
            fetchBtn.innerHTML = '❌ Failed to fetch data';
            console.error('Fetch error:', result.error || result);
            setTimeout(() => {
                fetchBtn.innerHTML = originalText;
                fetchBtn.disabled = false;
            }, 3000);
        }
    } catch (error) {
        fetchBtn.innerHTML = '❌ Error occurred';
        console.error('Fetch error:', error);
        setTimeout(() => {
            fetchBtn.innerHTML = originalText;
            fetchBtn.disabled = false;
        }, 3000);
    }
}

// Update selected components
function updateSelectedComponents() {
    const checkboxes = document.querySelectorAll('#componentGrid input[type="checkbox"]:checked');
    selectedComponents = Array.from(checkboxes).map(cb => cb.value);
    
    // Update count
    document.getElementById('selectedCount').textContent = `${selectedComponents.length} component${selectedComponents.length !== 1 ? 's' : ''} selected`;
    
    // Enable/disable view button
    document.getElementById('viewDashboardBtn').disabled = selectedComponents.length === 0;
}

// Generate dashboard for selected components using Flask API
async function generateExplorerDashboard() {
    if (selectedComponents.length === 0) return;
    
    console.log('Generating dashboard for:', selectedComponents);
    
    try {
        // Call Flask API with selected components
        const response = await fetch('/api/explorer/data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                components: selectedComponents
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Received data:', data);
        
        // Check if data has any content
        const hasData = data && data.summary && Object.keys(data.summary).length > 0;
        
        if (!hasData) {
            console.error('No data in response:', data);
            alert('No data available for selected components.\n\nPlease click "🔄 Fetch Latest Data" button first to collect defect data for all components.');
            return;
        }
        
        // Hide component selector, show dashboard
        document.querySelector('.component-explorer').style.display = 'none';
        document.getElementById('explorerDashboard').style.display = 'block';
        
        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
        
        // Render explorer dashboard with the data
        renderExplorerKPICards(data.summary);
        renderExplorerLineChart(data.dailyTrend);
        renderExplorerPieChart(data.componentBreakdown, data.summary);
        renderExplorerBarChart(data.componentBreakdown);
        renderExplorerComparisonChart(data.weekComparison);
        renderExplorerSOETriageTable(data.soeTriageDefects || []);
        
    } catch (error) {
        console.error('Error generating explorer dashboard:', error);
        alert('Error loading dashboard data. Please try again.');
    }
}

// LEGACY CODE BELOW - keeping for reference but not used
async function generateExplorerDashboard_OLD() {
    if (selectedComponents.length === 0) return;
    
    console.log('Generating dashboard for:', selectedComponents);
    
    // Get all components data
    const result = await chrome.storage.local.get(['allComponentsSnapshots']);
    const allSnapshots = result.allComponentsSnapshots || {};
    
    // Get last 7 days
    const dates = [];
    for (let i = 6; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        dates.push(date.toISOString().split('T')[0]);
    }
    
    // Aggregate data for selected components
    const aggregatedData = {};
    dates.forEach(date => {
        let total = 0, untriaged = 0, testBugs = 0, productBugs = 0, infraBugs = 0;
        
        selectedComponents.forEach(component => {
            const compData = allSnapshots[date]?.[component];
            if (compData) {
                total += compData.total || 0;
                untriaged += compData.untriaged || 0;
                testBugs += compData.testBugs || 0;
                productBugs += compData.productBugs || 0;
                infraBugs += compData.infraBugs || 0;
            }
        });
        
        aggregatedData[date] = { total, untriaged, testBugs, productBugs, infraBugs };
    });
    
    // Build dashboard data
    const latestDate = dates[dates.length - 1];
    const latestData = aggregatedData[latestDate] || {};
    
    // Calculate week comparison with fallback logic
    let lastWeekData = { total: 0, untriaged: 0 };
    let lastWeekDateUsed = null;
    
    // Get all available dates from allSnapshots
    const availableDates = Object.keys(allSnapshots).sort();
    console.log('Explorer: Available dates in allSnapshots:', availableDates);
    console.log('Explorer: Current week dates:', dates);
    
    // Strategy 1: Try 7 days before today, then try nearby dates
    const today = new Date();
    const lastWeekDate = new Date(today);
    lastWeekDate.setDate(lastWeekDate.getDate() - 7);
    const lastWeekDateStr = lastWeekDate.toISOString().split('T')[0];
    console.log('Explorer: Looking for last week date (7 days ago from today):', lastWeekDateStr);
    
    // Try the exact date first, then try 1-2 days before/after
    const datesToTry = [
        lastWeekDateStr,
        new Date(new Date(lastWeekDateStr).getTime() - 86400000).toISOString().split('T')[0], // -1 day
        new Date(new Date(lastWeekDateStr).getTime() + 86400000).toISOString().split('T')[0], // +1 day
        new Date(new Date(lastWeekDateStr).getTime() - 172800000).toISOString().split('T')[0], // -2 days
        new Date(new Date(lastWeekDateStr).getTime() + 172800000).toISOString().split('T')[0]  // +2 days
    ];
    
    let foundNearbyDate = null;
    for (const dateToTry of datesToTry) {
        if (allSnapshots[dateToTry]) {
            foundNearbyDate = dateToTry;
            console.log(`Explorer: Found nearby date: ${dateToTry}`);
            break;
        }
    }
    
    if (foundNearbyDate) {
        // Aggregate last week data for selected components
        let total = 0, untriaged = 0;
        selectedComponents.forEach(component => {
            const compData = allSnapshots[foundNearbyDate]?.[component];
            if (compData) {
                total += compData.total || 0;
                untriaged += compData.untriaged || 0;
            }
        });
        lastWeekData = { total, untriaged };
        lastWeekDateUsed = foundNearbyDate;
        console.log(`Explorer: Using last week data from ${foundNearbyDate}`, lastWeekData);
    } else {
        console.log('Explorer: No nearby date found, trying fallback strategy');
        // Strategy 2: Use oldest available snapshot that's at least 2 days before latest
        if (availableDates.length > 0) {
            // Find a date that's at least 2 days old and has data
            let foundDate = null;
            for (let i = 0; i < availableDates.length; i++) {
                const testDate = availableDates[i];
                const testDateObj = new Date(testDate);
                const daysDiff = Math.floor((new Date(latestDate) - testDateObj) / (1000 * 60 * 60 * 24));
                
                if (daysDiff >= 2) {
                    foundDate = testDate;
                    break;
                }
            }
            
            if (foundDate) {
                let total = 0, untriaged = 0;
                selectedComponents.forEach(component => {
                    const compData = allSnapshots[foundDate]?.[component];
                    if (compData) {
                        total += compData.total || 0;
                        untriaged += compData.untriaged || 0;
                    }
                });
                lastWeekData = { total, untriaged };
                lastWeekDateUsed = foundDate;
                const daysDiff = Math.floor((new Date(latestDate) - new Date(foundDate)) / (1000 * 60 * 60 * 24));
                console.log(`Explorer: Using oldest available snapshot from ${foundDate} (${daysDiff} days ago)`, lastWeekData);
            } else {
                console.log('Explorer: No suitable historical data found (need at least 2 days difference)');
            }
        } else {
            console.log('Explorer: No historical snapshots available');
        }
    }
    
    const dashboardData = {
        summary: {
            totalDefects: latestData.total || 0,
            untriaged: latestData.untriaged || 0,
            testBugs: latestData.testBugs || 0,
            productBugs: latestData.productBugs || 0,
            infraBugs: latestData.infraBugs || 0,
            trendPercentage: 0
        },
        dailyTrend: {
            labels: dates.map(d => new Date(d).toLocaleDateString('en-US', { weekday: 'short' })),
            total: dates.map(d => aggregatedData[d]?.total || 0),
            untriaged: dates.map(d => aggregatedData[d]?.untriaged || 0)
        },
        triageBreakdown: {
            untriaged: latestData.untriaged || 0,
            testBug: latestData.testBugs || 0,
            productBug: latestData.productBugs || 0,
            infrastructure: latestData.infraBugs || 0
        },
        componentBreakdown: {
            labels: selectedComponents,
            total: selectedComponents.map(comp => allSnapshots[latestDate]?.[comp]?.total || 0),
            untriaged: selectedComponents.map(comp => allSnapshots[latestDate]?.[comp]?.untriaged || 0),
            testBugs: selectedComponents.map(comp => allSnapshots[latestDate]?.[comp]?.testBugs || 0),
            productBugs: selectedComponents.map(comp => allSnapshots[latestDate]?.[comp]?.productBugs || 0),
            infraBugs: selectedComponents.map(comp => allSnapshots[latestDate]?.[comp]?.infraBugs || 0)
        },
        weekComparison: {
            lastWeek: lastWeekData,
            thisWeek: { total: latestData.total || 0, untriaged: latestData.untriaged || 0 },
            lastWeekDate: lastWeekDateUsed
        }
    };
    
    // Hide selector, show dashboard
    document.querySelector('.component-explorer').style.display = 'none';
    document.getElementById('explorerDashboard').style.display = 'block';
    
    // Render charts
    console.log('Explorer: Rendering charts with weekComparison:', dashboardData.weekComparison);
    renderExplorerKPICards(dashboardData.summary);
    renderExplorerLineChart(dashboardData.dailyTrend);
    renderExplorerPieChart(dashboardData.componentBreakdown, dashboardData.summary);
    renderExplorerBarChart(dashboardData.componentBreakdown);
    renderExplorerComparisonChart(dashboardData.weekComparison);
    
    // Render SOE Triage table for selected components
    renderExplorerSOETriageTable(selectedComponents);
    
    // Scroll to top of dashboard
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Render SOE Triage table for explorer - receives defects array directly from API
async function renderExplorerSOETriageTable(defectsArray) {
    const tbody = document.getElementById('explorerDefectsTableBody');
    
    // defectsArray is already filtered by the API for selected components
    const filteredDefects = defectsArray || [];
    
    if (filteredDefects.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 20px; color: #8899a6;">
                    ✅ No overdue SOE triage defects found for selected components
                </td>
            </tr>
        `;
    } else {
        tbody.innerHTML = filteredDefects.map(defect => `
            <tr>
                <td>
                    <a href="https://wasrtc.hursley.ibm.com:9443/jazz/web/projects/WS-CD#action=com.ibm.team.workitem.viewWorkItem&id=${defect.id}"
                       target="_blank"
                       class="defect-id"
                       style="color: #1d9bf0; text-decoration: none;">
                        ${defect.id}
                    </a>
                </td>
                <td title="${defect.summary}">${defect.summary}</td>
                <td>${defect.functionalArea}</td>
                <td>${defect.filedAgainst}</td>
                <td>${defect.creationDate}</td>
                <td>${defect.ownedBy}</td>
            </tr>
        `).join('');
    }
}

// Render explorer KPI cards
function renderExplorerKPICards(summary) {
    const kpiRow = document.getElementById('explorerKpiRow');
    const totalDefects = summary.total || summary.totalDefects || 0;
    const untriaged = summary.untriaged || 0;
    const testBugs = summary.test_bugs || summary.testBugs || 0;
    const productBugs = summary.product_bugs || summary.productBugs || 0;
    const infraBugs = summary.infra_bugs || summary.infraBugs || 0;
    
    const untriagedPercent = totalDefects > 0
        ? Math.round((untriaged / totalDefects) * 100)
        : 0;
    const slaCompliance = Math.max(0, Math.min(100, 100 - untriagedPercent));
    
    kpiRow.innerHTML = `
        <div class="kpi-card" style="animation-delay: 0s;">
            <div class="icon">🏆</div>
            <div class="label">Total Defects</div>
            <div class="value">${totalDefects}</div>
        </div>
        <div class="kpi-card" style="animation-delay: 0.1s;">
            <div class="icon">📍</div>
            <div class="label">Untriaged</div>
            <div class="value">${untriaged}</div>
            <div class="change neutral">${untriagedPercent}% of total</div>
        </div>
        <div class="kpi-card" style="animation-delay: 0.2s;">
            <div class="icon">⭐</div>
            <div class="label">Test Bugs</div>
            <div class="value">${testBugs}</div>
        </div>
        <div class="kpi-card" style="animation-delay: 0.3s;">
            <div class="icon">🔒</div>
            <div class="label">Product Bugs</div>
            <div class="value">${productBugs}</div>
        </div>
        <div class="kpi-card" style="animation-delay: 0.4s;">
            <div class="icon">🔮</div>
            <div class="label">Infrastructure Issues</div>
            <div class="value">${infraBugs}</div>
        </div>
        <div class="kpi-card" style="animation-delay: 0.5s;">
            <div class="label">SLA Compliance</div>
            <div style="position: relative; height: 70px; margin: 6px 0;">
                <svg class="progress-ring" width="70" height="70">
                    <circle stroke="rgba(255,255,255,0.1)" stroke-width="6" fill="transparent" r="30" cx="35" cy="35"/>
                    <circle class="progress-ring-circle" stroke="#00d4aa" stroke-width="6" fill="transparent" r="30" cx="35" cy="35"
                        stroke-dasharray="188" stroke-dashoffset="${188 - (188 * slaCompliance) / 100}" stroke-linecap="round"/>
                </svg>
                <div class="progress-value">${slaCompliance}%</div>
            </div>
        </div>
    `;
}

// Render explorer charts (similar to main dashboard but with explorer canvas IDs)
function renderExplorerLineChart(dailyTrend) {
    const ctx = document.getElementById('explorerLineChart').getContext('2d');
    if (chartInstances.explorerLineChart) chartInstances.explorerLineChart.destroy();
    
    Chart.defaults.color = '#8899a6';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';
    
    chartInstances.explorerLineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dailyTrend.labels,
            datasets: [{
                label: 'Total Defects',
                data: dailyTrend.total,
                borderColor: '#1d9bf0',
                backgroundColor: 'rgba(29, 155, 240, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2,
                pointRadius: 3,
                pointHoverRadius: 5,
                pointBackgroundColor: '#1d9bf0',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }, {
                label: 'Untriaged',
                data: dailyTrend.untriaged,
                borderColor: '#ff6b9d',
                backgroundColor: 'rgba(255, 107, 157, 0.1)',
                tension: 0.4,
                fill: true,
                borderWidth: 2,
                pointRadius: 3,
                pointHoverRadius: 5,
                pointBackgroundColor: '#ff6b9d',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, position: 'top', labels: { color: '#e1e8ed', font: { size: 11, weight: '600' }, padding: 8, usePointStyle: true, boxWidth: 8, boxHeight: 8 } },
                tooltip: { backgroundColor: '#1a1f3a', titleColor: '#fff', bodyColor: '#e1e8ed', borderColor: 'rgba(255, 255, 255, 0.1)', borderWidth: 1, padding: 8, displayColors: true, bodyFont: { size: 10 }, titleFont: { size: 10 } }
            },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false }, ticks: { color: '#8899a6', font: { size: 10 } } },
                y: { beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false }, ticks: { color: '#8899a6', font: { size: 10 }, stepSize: 20 } }
            }
        }
    });
}

function renderExplorerPieChart(componentBreakdown, summary) {
    const ctx = document.getElementById('explorerPieChart').getContext('2d');
    if (chartInstances.explorerPieChart) chartInstances.explorerPieChart.destroy();
    
    // Get component data
    const components = componentBreakdown.labels || [];
    const totals = componentBreakdown.total || [];
    
    // Generate colors for each component
    const colors = [
        '#ff6b9d', '#ffad1f', '#1d9bf0', '#00d4aa',
        '#a78bfa', '#fb923c', '#34d399', '#f472b6',
        '#60a5fa', '#fbbf24', '#4ade80', '#c084fc'
    ];
    
    chartInstances.explorerPieChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: components,
            datasets: [{
                data: totals,
                backgroundColor: colors.slice(0, components.length),
                borderWidth: 0,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: { position: 'bottom', labels: { color: '#e1e8ed', font: { size: 10, weight: '600' }, padding: 8, usePointStyle: true, boxWidth: 8, boxHeight: 8 } },
                tooltip: {
                    backgroundColor: '#1a1f3a',
                    titleColor: '#fff',
                    bodyColor: '#e1e8ed',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 8,
                    bodyFont: { size: 10 },
                    titleFont: { size: 10 },
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        },
        plugins: [{
            beforeDraw: function(chart) {
                const width = chart.width, height = chart.height, ctx = chart.ctx;
                ctx.restore();
                const fontSize = (height / 130).toFixed(2);
                ctx.font = `bold ${fontSize}em sans-serif`;
                ctx.textBaseline = 'middle';
                ctx.fillStyle = '#fff';
                const text = (summary.total || summary.totalDefects || 0).toString();
                const textX = Math.round((width - ctx.measureText(text).width) / 2);
                const textY = height / 2 - 8;
                ctx.fillText(text, textX, textY);
                ctx.font = `${fontSize * 0.4}em sans-serif`;
                ctx.fillStyle = '#8899a6';
                const subtext = 'Total';
                const subtextX = Math.round((width - ctx.measureText(subtext).width) / 2);
                ctx.fillText(subtext, subtextX, textY + 18);
                ctx.save();
            }
        }]
    });
}

function renderExplorerBarChart(componentBreakdown) {
    const ctx = document.getElementById('explorerBarChart').getContext('2d');
    if (chartInstances.explorerBarChart) chartInstances.explorerBarChart.destroy();
    
    chartInstances.explorerBarChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: componentBreakdown.labels,
            datasets: [{
                label: 'Untriaged',
                data: componentBreakdown.untriaged,
                backgroundColor: '#ff6b9d',
                borderRadius: 4,
                barThickness: 15
            }, {
                label: 'Test Bugs',
                data: componentBreakdown.testBugs,
                backgroundColor: '#ffad1f',
                borderRadius: 4,
                barThickness: 15
            }, {
                label: 'Product Bugs',
                data: componentBreakdown.productBugs,
                backgroundColor: '#1d9bf0',
                borderRadius: 4,
                barThickness: 15
            }, {
                label: 'Infrastructure',
                data: componentBreakdown.infraBugs,
                backgroundColor: '#00d4aa',
                borderRadius: 4,
                barThickness: 15
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { color: '#e1e8ed', font: { size: 10, weight: '600' }, padding: 8, usePointStyle: true, boxWidth: 8, boxHeight: 8 } },
                tooltip: { backgroundColor: '#1a1f3a', titleColor: '#fff', bodyColor: '#e1e8ed', borderColor: 'rgba(255, 255, 255, 0.1)', borderWidth: 1, padding: 8, bodyFont: { size: 10 }, titleFont: { size: 10 } }
            },
            scales: {
                x: { stacked: true, grid: { display: false }, ticks: { color: '#8899a6', font: { size: 9 } } },
                y: { stacked: true, beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false }, ticks: { color: '#8899a6', font: { size: 9 } } }
            }
        }
    });
}

function renderExplorerComparisonChart(weekComparison) {
    const ctx = document.getElementById('explorerComparisonChart').getContext('2d');
    if (chartInstances.explorerComparisonChart) chartInstances.explorerComparisonChart.destroy();
    
    Chart.defaults.color = '#8899a6';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';
    
    console.log('renderExplorerComparisonChart called with:', weekComparison);
    
    // Check if we have last week data
    const hasLastWeekData = weekComparison &&
                           weekComparison.lastWeek &&
                           weekComparison.lastWeek.total > 0;
    
    console.log('hasLastWeekData:', hasLastWeekData);
    console.log('lastWeek data:', weekComparison?.lastWeek);
    console.log('thisWeek data:', weekComparison?.thisWeek);
    
    // Build labels with dates for clarity
    let lastWeekLabel = 'Previous';
    if (hasLastWeekData && weekComparison.lastWeekDate) {
        const date = new Date(weekComparison.lastWeekDate);
        lastWeekLabel = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    
    // If no last week data, show only this week
    const labels = hasLastWeekData ? [lastWeekLabel, 'This Week'] : ['This Week'];
    const totalData = hasLastWeekData
        ? [weekComparison.lastWeek.total, weekComparison.thisWeek.total]
        : [weekComparison.thisWeek.total];
    const untriagedData = hasLastWeekData
        ? [weekComparison.lastWeek.untriaged, weekComparison.thisWeek.untriaged]
        : [weekComparison.thisWeek.untriaged];
    
    chartInstances.explorerComparisonChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Total',
                data: totalData,
                backgroundColor: '#1d9bf0',
                borderRadius: 6,
                barThickness: 50
            }, {
                label: 'Untriaged',
                data: untriagedData,
                backgroundColor: '#ff6b9d',
                borderRadius: 6,
                barThickness: 50
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, position: 'top', labels: { color: '#e1e8ed', font: { size: 11, weight: '600' }, padding: 10, usePointStyle: true, boxWidth: 8, boxHeight: 8 } },
                tooltip: { backgroundColor: '#1a1f3a', titleColor: '#fff', bodyColor: '#e1e8ed', borderColor: 'rgba(255, 255, 255, 0.1)', borderWidth: 1, padding: 10, bodyFont: { size: 11 }, titleFont: { size: 11 } }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: '#e1e8ed', font: { size: 11, weight: '600' } } },
                y: { beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false }, ticks: { color: '#8899a6', font: { size: 10 } } }
            }
        }
    });
}

// Initialize component explorer on page load (no tabs, direct access)
document.addEventListener('DOMContentLoaded', () => {
    const grid = document.getElementById('componentGrid');
    if (grid && (!grid.children || grid.children.length === 0)) {
        initializeComponentExplorer();
    }
});

// Made with Bob
