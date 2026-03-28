// ============================================
// EZFOODZ Restaurant Dashboard — app.js
// ============================================

const API = window.location.origin; // FastAPI root
let TOKEN = '';
let RESTAURANT_ID = null;
let RESTAURANT_DATA = {};
let pollInterval = null;

// ============================================
// LOGIN
// ============================================
async function doLogin() {
    const email = document.getElementById('loginEmail').value;
    const pass = document.getElementById('loginPassword').value;
    const errEl = document.getElementById('loginError');

    if (!email || !pass) { errEl.textContent = 'Please fill in all fields'; return; }

    try {
        const fd = new FormData();
        fd.append('email', email);
        fd.append('password', pass);

        const res = await fetch(`${API}/restaurant/login`, { method: 'POST', body: fd });
        if (!res.ok) {
            const err = await res.json();
            errEl.textContent = err.detail || 'Login failed';
            return;
        }

        const data = await res.json();
        TOKEN = data.token;
        RESTAURANT_ID = data.restaurant_id;

        document.getElementById('loginPage').style.display = 'none';
        document.getElementById('dashboardPage').style.display = 'block';

        loadDashboard();
        startPolling();
    } catch (e) {
        errEl.textContent = 'Connection failed. Is the server running?';
    }
}

function doLogout() {
    TOKEN = '';
    RESTAURANT_ID = null;
    stopPolling();
    document.getElementById('dashboardPage').style.display = 'none';
    document.getElementById('loginPage').style.display = 'flex';
    document.getElementById('loginPassword').value = '';
    document.getElementById('loginError').textContent = '';
}

// ============================================
// DASHBOARD INIT
// ============================================
async function loadDashboard() {
    await loadRestaurantInfo();
    await loadItems();
    await loadOrders();
    await loadHistory();
}

async function loadRestaurantInfo() {
    const res = await fetch(`${API}/restaurant/me`, {
        headers: { 'Authorization': `Bearer ${TOKEN}` }
    });
    RESTAURANT_DATA = await res.json();

    document.getElementById('headerRestName').textContent = RESTAURANT_DATA.name;
    updateStatusUI(RESTAURANT_DATA.is_open);

    // Fill details form
    document.getElementById('detailName').value = RESTAURANT_DATA.name || '';
    document.getElementById('detailDescription').value = RESTAURANT_DATA.description || '';
    document.getElementById('detailCuisine').value = RESTAURANT_DATA.cuisine_type || '';
    document.getElementById('detailAddress').value = RESTAURANT_DATA.address || '';
    document.getElementById('detailPhone').value = RESTAURANT_DATA.phone || '';

    if (RESTAURANT_DATA.image_path) {
        const img = document.getElementById('restaurantImage');
        img.src = `${API}/uploads/${RESTAURANT_DATA.image_path}`;
        img.style.display = 'block';
        document.getElementById('imageUploadText').textContent = 'Click to change image';
    }
}

function updateStatusUI(isOpen) {
    const badge = document.getElementById('headerStatus');
    const text = document.getElementById('headerStatusText');
    const btn = document.getElementById('toggleBtn');

    if (isOpen) {
        badge.className = 'status-badge status-open';
        text.textContent = 'OPEN';
        btn.textContent = 'Close Restaurant';
        btn.className = 'toggle-btn toggle-open';
    } else {
        badge.className = 'status-badge status-closed';
        text.textContent = 'CLOSED';
        btn.textContent = 'Open Restaurant';
        btn.className = 'toggle-btn toggle-close';
    }
}

// ============================================
// TOGGLE OPEN / CLOSE
// ============================================
async function toggleOpenClose() {
    const res = await fetch(`${API}/restaurants/${RESTAURANT_ID}/toggle`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${TOKEN}` }
    });
    const data = await res.json();
    RESTAURANT_DATA.is_open = data.is_open ? 1 : 0;
    updateStatusUI(data.is_open);
    showToast(data.is_open ? 'Restaurant is now OPEN' : 'Restaurant is now CLOSED', 'success');
}

// ============================================
// NAV TABS
// ============================================
function switchTab(el) {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');

    const section = el.getAttribute('data-section');
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById(`sec-${section}`).classList.add('active');

    // Refresh data when switching
    if (section === 'items') loadItems();
    if (section === 'orders') loadOrders();
    if (section === 'history') loadHistory();
    if (section === 'addItem') resetAddForm();
}

// ============================================
// ITEMS IN STOCK
// ============================================
async function loadItems() {
    const res = await fetch(`${API}/menu/${RESTAURANT_ID}?all=true`);
    const data = await res.json();
    const container = document.getElementById('itemsList');

    if (data.items.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No items yet</h3>
                <p>Add your first menu item to get started</p>
            </div>`;
        return;
    }

    container.innerHTML = data.items.map(item => `
        <div class="item-row">
            <div class="item-info">
                <span class="item-name">${esc(item.name)}</span>
                <div class="item-meta">
                    <span class="badge badge-${item.category === 'non-veg' ? 'nonveg' : item.category}">${item.category}</span>
                    ${item.cuisine ? `<span style="font-size:12px;color:var(--text-muted)">${esc(item.cuisine)}</span>` : ''}
                </div>
            </div>
            <span class="item-price">₹${item.price}</span>
            <div class="item-actions">
                <label class="switch">
                    <input type="checkbox" ${item.is_available ? 'checked' : ''} onchange="toggleItem(${item.id})">
                    <span class="slider"></span>
                </label>
                <button class="btn btn-yellow btn-sm" onclick="openEditModal(${item.id},'${esc(item.name)}','${item.category}','${esc(item.cuisine)}',${item.price})">Edit</button>
                <button class="btn btn-red btn-sm" onclick="deleteItem(${item.id})">Delete</button>
            </div>
        </div>
    `).join('');
}

async function toggleItem(itemId) {
    await fetch(`${API}/menu/item/${itemId}/toggle`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${TOKEN}` }
    });
    showToast('Availability updated', 'success');
}

async function deleteItem(itemId) {
    if (!confirm('Delete this item?')) return;
    await fetch(`${API}/menu/item/${itemId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${TOKEN}` }
    });
    showToast('Item deleted', 'success');
    loadItems();
}

// ============================================
// ADD ITEM
// ============================================
function resetAddForm() {
    document.getElementById('addItemTitle').textContent = 'Add New Item';
    document.getElementById('editItemId').value = '';
    document.getElementById('itemName').value = '';
    document.getElementById('itemCuisine').value = '';
    document.getElementById('itemPrice').value = '';
    // Reset category to veg
    document.querySelectorAll('#categoryGroup .radio-option').forEach(el => el.classList.remove('selected'));
    document.querySelector('#categoryGroup .radio-option').classList.add('selected');
    document.querySelector('#categoryGroup input[value="veg"]').checked = true;
}

function selectRadio(el, groupName) {
    el.closest('.radio-group').querySelectorAll('.radio-option').forEach(o => o.classList.remove('selected'));
    el.classList.add('selected');
    el.querySelector('input').checked = true;
}

async function saveItem() {
    const name = document.getElementById('itemName').value;
    const category = document.querySelector('input[name="category"]:checked').value;
    const cuisine = document.getElementById('itemCuisine').value;
    const price = document.getElementById('itemPrice').value;

    if (!name || !price) {
        showToast('Name and price are required', 'error');
        return;
    }

    const fd = new FormData();
    fd.append('name', name);
    fd.append('category', category);
    fd.append('cuisine', cuisine);
    fd.append('price', price);

    const res = await fetch(`${API}/menu/${RESTAURANT_ID}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${TOKEN}` },
        body: fd
    });

    if (res.ok) {
        showToast('Item added successfully!', 'success');
        resetAddForm();
        switchTab(document.querySelector('[data-section="items"]'));
    } else {
        showToast('Failed to add item', 'error');
    }
}

function cancelEdit() {
    resetAddForm();
    switchTab(document.querySelector('[data-section="items"]'));
}

// ============================================
// EDIT ITEM MODAL
// ============================================
function openEditModal(id, name, category, cuisine, price) {
    document.getElementById('modalItemId').value = id;
    document.getElementById('modalItemName').value = name;
    document.getElementById('modalItemCategory').value = category;
    document.getElementById('modalItemCuisine').value = cuisine;
    document.getElementById('modalItemPrice').value = price;
    document.getElementById('editModal').classList.add('show');
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('show');
}

async function saveEditModal() {
    const id = document.getElementById('modalItemId').value;
    const fd = new FormData();
    fd.append('name', document.getElementById('modalItemName').value);
    fd.append('category', document.getElementById('modalItemCategory').value);
    fd.append('cuisine', document.getElementById('modalItemCuisine').value);
    fd.append('price', document.getElementById('modalItemPrice').value);

    const res = await fetch(`${API}/menu/item/${id}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${TOKEN}` },
        body: fd
    });

    if (res.ok) {
        showToast('Item updated!', 'success');
        closeEditModal();
        loadItems();
    } else {
        showToast('Update failed', 'error');
    }
}

// ============================================
// RESTAURANT DETAILS
// ============================================
async function saveDetails() {
    const fd = new FormData();
    fd.append('name', document.getElementById('detailName').value);
    fd.append('description', document.getElementById('detailDescription').value);
    fd.append('cuisine_type', document.getElementById('detailCuisine').value);
    fd.append('address', document.getElementById('detailAddress').value);
    fd.append('phone', document.getElementById('detailPhone').value);

    const res = await fetch(`${API}/restaurants/${RESTAURANT_ID}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${TOKEN}` },
        body: fd
    });

    if (res.ok) {
        showToast('Details saved!', 'success');
        loadRestaurantInfo();
    } else {
        showToast('Failed to save details', 'error');
    }
}

async function uploadImage(event) {
    const file = event.target.files[0];
    if (!file) return;

    const fd = new FormData();
    fd.append('file', file);

    const res = await fetch(`${API}/restaurants/${RESTAURANT_ID}/image`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${TOKEN}` },
        body: fd
    });

    if (res.ok) {
        const data = await res.json();
        const img = document.getElementById('restaurantImage');
        img.src = `${API}${data.image_url}`;
        img.style.display = 'block';
        document.getElementById('imageUploadText').textContent = 'Click to change image';
        showToast('Image uploaded!', 'success');
    } else {
        showToast('Image upload failed', 'error');
    }
}

// ============================================
// CURRENT ORDERS
// ============================================
async function loadOrders() {
    try {
        const res = await fetch(`${API}/orders/restaurant/${RESTAURANT_ID}`, {
            headers: { 'Authorization': `Bearer ${TOKEN}` }
        });
        const data = await res.json();
        const container = document.getElementById('ordersList');

        if (data.orders.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No active orders</h3>
                    <p>New orders will appear here automatically</p>
                </div>`;
            return;
        }

        container.innerHTML = data.orders.map(order => `
            <div class="order-card">
                <div class="order-header">
                    <span class="order-code">${esc(order.secret_code)}</span>
                    <span class="order-status order-status-${order.status}">${order.status.toUpperCase()}</span>
                </div>
                <ul class="order-items-list">
                    ${order.items.map(i => `
                        <li>
                            <span>${esc(i.item_name)} × ${i.quantity}</span>
                            <span>₹${(i.price * i.quantity).toFixed(0)}</span>
                        </li>
                    `).join('')}
                </ul>
                <div class="order-footer">
                    <span class="order-total">Total: ₹${order.total}</span>
                    <div style="display:flex; gap:8px; align-items:center;">
                        <span class="order-time">${formatTime(order.created_at)}</span>
                        ${getStatusButton(order)}
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        // Silently fail during polling
    }
}

function getStatusButton(order) {
    if (order.status === 'preparing') {
        return `<button class="btn btn-green btn-sm" onclick="updateOrderStatus(${order.id},'ready')">Mark Ready</button>`;
    } else if (order.status === 'ready') {
        return `<button class="btn btn-blue btn-sm" onclick="updateOrderStatus(${order.id},'given')">Mark Given</button>`;
    }
    return '';
}

async function updateOrderStatus(orderId, newStatus) {
    const res = await fetch(`${API}/orders/${orderId}/status`, {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${TOKEN}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ status: newStatus })
    });

    if (res.ok) {
        showToast(`Order marked as ${newStatus}`, 'success');
        loadOrders();
        loadHistory();
    } else {
        showToast('Failed to update order', 'error');
    }
}

// ============================================
// ORDER HISTORY
// ============================================
async function loadHistory() {
    try {
        const res = await fetch(`${API}/orders/restaurant/${RESTAURANT_ID}/history`, {
            headers: { 'Authorization': `Bearer ${TOKEN}` }
        });
        const data = await res.json();
        const container = document.getElementById('historyList');

        if (data.orders.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No order history yet</h3>
                    <p>Completed orders will appear here</p>
                </div>`;
            return;
        }

        container.innerHTML = data.orders.map(order => `
            <div class="order-card" style="opacity:0.8;">
                <div class="order-header">
                    <span class="order-code">${esc(order.secret_code)}</span>
                    <span class="order-status order-status-given">COMPLETED</span>
                </div>
                <ul class="order-items-list">
                    ${order.items.map(i => `
                        <li>
                            <span>${esc(i.item_name)} × ${i.quantity}</span>
                            <span>₹${(i.price * i.quantity).toFixed(0)}</span>
                        </li>
                    `).join('')}
                </ul>
                <div class="order-footer">
                    <span class="order-total">Total: ₹${order.total}</span>
                    <span class="order-time">${formatTime(order.created_at)}</span>
                </div>
            </div>
        `).join('');
    } catch (e) {
        // Silently fail
    }
}

// ============================================
// POLLING
// ============================================
function startPolling() {
    pollInterval = setInterval(() => {
        loadOrders();
    }, 5000);
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// ============================================
// UTILITIES
// ============================================
function esc(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

function formatTime(ts) {
    if (!ts) return '';
    const d = new Date(ts + 'Z');
    return d.toLocaleString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        day: '2-digit',
        month: 'short'
    });
}

function showToast(msg, type = 'success') {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toastMsg');
    toastMsg.textContent = msg;
    toast.className = `toast show ${type}`;
    setTimeout(() => { toast.className = 'toast'; }, 3000);
}

// Allow Enter key on login
document.getElementById('loginPassword').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') doLogin();
});
document.getElementById('loginRestaurantId').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') document.getElementById('loginPassword').focus();
});
