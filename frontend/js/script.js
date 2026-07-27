/**
 * Alab-Mart Store Controller
 * Product rendering, filtering, cart management, auth, checkout,
 * and the Alab shopping-voice-assistant widget.
 *
 * NOTE: Product objects from the backend use the field "name" (not "title").
 */

const CART_KEY = 'alab_mart_cart';
const USER_KEY = 'alab_mart_user';
const SESSION_KEY = 'alab_mart_session_id';

class StoreApp {
  constructor() {
    this.products = [];
    this.cart = JSON.parse(localStorage.getItem(CART_KEY) || '[]');
    this.currentUser = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    this.currentCategory = 'books';
    this.searchQuery = '';
    this.categoryLabels = {
      books: 'AI Books',
      hardware: 'AI Hardware Devices',
      assistants: 'AI Smart Assistants'
    };
  }

  async init() {
    await this.loadProducts();
    this.renderProducts();
    this.renderCart();
    this.renderAuthStatus();
  }

  async loadProducts() {
    try {
      this.products = await API.getProducts();
    } catch (err) {
      console.error('Failed to load products:', err);
      const grid = document.getElementById('productGrid');
      if (grid) grid.innerHTML = `<div class="no-products">Couldn't reach the Alabmart server. Is the backend running?</div>`;
    }
  }

  // ---------- CATEGORY + SEARCH ----------

  selectCategory(category, el) {
    this.currentCategory = category;
    this.searchQuery = '';
    const searchInput = document.getElementById('searchInput');
    if (searchInput) searchInput.value = '';

    document.querySelectorAll('.category-item').forEach(li => li.classList.remove('active'));
    if (el) el.classList.add('active');

    const titleEl = document.getElementById('categoryTitle');
    if (titleEl) titleEl.innerText = this.categoryLabels[category] || category;

    this.renderProducts();
  }

  handleSearch() {
    const input = document.getElementById('searchInput');
    this.searchQuery = (input ? input.value : '').toLowerCase().trim();
    this.renderProducts();
  }

  getFilteredProducts() {
    return this.products.filter(p => {
      const matchesCategory = !this.searchQuery ? p.category === this.currentCategory : true;
      const matchesSearch = !this.searchQuery ||
        p.name.toLowerCase().includes(this.searchQuery) ||
        (p.brand || '').toLowerCase().includes(this.searchQuery);
      return matchesCategory && matchesSearch;
    });
  }

  renderProducts() {
    const grid = document.getElementById('productGrid');
    const itemCount = document.getElementById('itemCount');
    if (!grid) return;

    const filtered = this.getFilteredProducts();
    if (itemCount) itemCount.innerText = `Showing ${filtered.length} Item${filtered.length === 1 ? '' : 's'}`;

    if (filtered.length === 0) {
      grid.innerHTML = `<div class="no-products">No AI products found matching your criteria.</div>`;
      return;
    }

    grid.innerHTML = filtered.map(product => `
      <div class="product-card">
        <img src="${product.image}" alt="${this.escapeHtml(product.name)}" class="product-img" onerror="this.src='https://via.placeholder.com/220x180?text=Alabmart'">
        <h3 class="product-title">${this.escapeHtml(product.name)}</h3>
        <p class="product-brand">${this.escapeHtml(product.brand || '')}</p>
        <p class="product-price">Rs.${product.price.toLocaleString('en-IN')}</p>
        <button class="add-cart-btn" onclick="window.storeApp.addToCart(${product.id})">Add to Cart</button>
      </div>
    `).join('');
  }

  escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, s => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[s]));
  }

  // ---------- CART ----------

  addToCart(productId, quantity = 1) {
    const product = this.products.find(p => p.id === productId);
    if (!product) return;

    const existing = this.cart.find(item => item.id === productId);
    if (existing) {
      existing.quantity += quantity;
    } else {
      this.cart.push({ ...product, quantity });
    }
    this.saveAndRenderCart();
  }

  removeFromCart(productId) {
    this.cart = this.cart.filter(item => item.id !== productId);
    this.saveAndRenderCart();
  }

  updateQuantity(productId, delta) {
    const item = this.cart.find(i => i.id === productId);
    if (!item) return;
    item.quantity += delta;
    if (item.quantity <= 0) {
      this.removeFromCart(productId);
    } else {
      this.saveAndRenderCart();
    }
  }

  syncCart(newCart) {
    if (Array.isArray(newCart)) {
      this.cart = newCart;
      this.saveAndRenderCart();
    }
  }

  saveAndRenderCart() {
    localStorage.setItem(CART_KEY, JSON.stringify(this.cart));
    this.renderCart();
  }

  cartTotal() {
    return this.cart.reduce((sum, i) => sum + i.price * i.quantity, 0);
  }

  renderCart() {
    const countEl = document.getElementById('cartCount');
    const totalEl = document.getElementById('cartTotal');
    const container = document.getElementById('cartItemsContainer');

    const totalCount = this.cart.reduce((sum, i) => sum + i.quantity, 0);
    if (countEl) countEl.innerText = totalCount;
    if (totalEl) totalEl.innerText = this.cartTotal().toLocaleString('en-IN');

    if (!container) return;

    if (this.cart.length === 0) {
      container.innerHTML = `<p class="muted-text">Your cart is empty.</p>`;
      return;
    }

    container.innerHTML = this.cart.map(item => `
      <div class="cart-item">
        <span class="cart-item-name">${this.escapeHtml(item.name)}<br><small>Rs.${item.price.toLocaleString('en-IN')} x ${item.quantity}</small></span>
        <button class="icon-btn" onclick="window.storeApp.updateQuantity(${item.id}, -1)">-</button>
        <span>${item.quantity}</span>
        <button class="icon-btn" onclick="window.storeApp.updateQuantity(${item.id}, 1)">+</button>
        <button class="icon-btn" onclick="window.storeApp.removeFromCart(${item.id})">&times;</button>
      </div>
    `).join('');
  }

  toggleCartModal(show) {
    const modal = document.getElementById('cartModal');
    if (modal) modal.style.display = show === false ? 'none' : (show === true ? 'flex' : (modal.style.display === 'flex' ? 'none' : 'flex'));
  }

  // ---------- CHECKOUT ----------

  checkout() {
    if (this.cart.length === 0) {
      alert('Your cart is empty!');
      return;
    }
    if (!this.currentUser) {
      this.toggleCartModal(false);
      alert('Please log in first to check out.');
      this.toggleAuthModal(true);
      return;
    }

    this.toggleCartModal(false);
    const itemsEl = document.getElementById('checkoutItems');
    const totalEl = document.getElementById('checkoutTotal');
    if (itemsEl) {
      itemsEl.innerHTML = this.cart.map(i =>
        `<div>${this.escapeHtml(i.name)} &times; ${i.quantity} &mdash; Rs.${(i.price * i.quantity).toLocaleString('en-IN')}</div>`
      ).join('');
    }
    if (totalEl) totalEl.innerText = this.cartTotal().toLocaleString('en-IN');
    this.toggleCheckoutModal(true);
  }

  toggleCheckoutModal(show) {
    const modal = document.getElementById('checkoutModal');
    if (modal) modal.style.display = show === false ? 'none' : (show === true ? 'flex' : (modal.style.display === 'flex' ? 'none' : 'flex'));
  }

  async placeOrder(event) {
    event.preventDefault();
    if (!this.currentUser) {
      alert('Please log in first.');
      return;
    }
    const form = event.target;
    const paymentMethod = form.paymentMethod.value;

    try {
      const result = await API.checkout({
        user_id: this.currentUser.id,
        items: this.cart,
        total: this.cartTotal(),
        payment_method: paymentMethod
      });
      if (result.success) {
        alert(`Order placed! Order #${result.order.id} - ${result.order.status}`);
        this.cart = [];
        this.saveAndRenderCart();
        this.toggleCheckoutModal(false);
      } else {
        alert('Checkout failed. Please try again.');
      }
    } catch (err) {
      console.error('Checkout error:', err);
      alert('Checkout failed. Please try again.');
    }
  }

  // ---------- AUTH ----------

  toggleAuthModal(show) {
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = show === false ? 'none' : (show === true ? 'flex' : (modal.style.display === 'flex' ? 'none' : 'flex'));
  }

  async handleAuth(event, mode) {
    event.preventDefault();
    const form = event.target;
    const email = form.email.value.trim();
    const password = form.password.value;

    if (mode === 'register') {
      const confirmPassword = form.confirmPassword.value;
      if (password !== confirmPassword) {
        alert("Passwords don't match.");
        return;
      }
    }

    try {
      const result = mode === 'login'
        ? await API.login(email, password)
        : await API.register(email, password);

      if (result.success) {
        this.currentUser = result.user;
        localStorage.setItem(USER_KEY, JSON.stringify(this.currentUser));
        this.renderAuthStatus();
        this.toggleAuthModal(false);
        form.reset();
      }
    } catch (err) {
      alert(err.message || `${mode === 'login' ? 'Login' : 'Registration'} failed.`);
    }
  }

  logout() {
    this.currentUser = null;
    localStorage.removeItem(USER_KEY);
    this.renderAuthStatus();
  }

  renderAuthStatus() {
    const authStatus = document.getElementById('authStatus');
    if (!authStatus) return;

    if (this.currentUser) {
      authStatus.innerHTML = `
        <span>${this.escapeHtml(this.currentUser.email)}</span>
        <button onclick="window.storeApp.logout()">Logout</button>
      `;
    } else {
      authStatus.innerHTML = `<button onclick="window.storeApp.toggleAuthModal(true)">Login</button>`;
    }
  }
}

// ---------- GLOBAL WRAPPER FUNCTIONS (called via inline onclick in index.html) ----------

function handleSearch() { window.storeApp.handleSearch(); }
function selectCategory(cat, el) { window.storeApp.selectCategory(cat, el); }
function toggleCartModal(show) { window.storeApp.toggleCartModal(show); }
function checkout() { window.storeApp.checkout(); }
function toggleCheckoutModal(show) { window.storeApp.toggleCheckoutModal(show); }
function placeOrder(event) { window.storeApp.placeOrder(event); }
function toggleAuthModal(show) { window.storeApp.toggleAuthModal(show); }
function handleAuth(event, mode) { window.storeApp.handleAuth(event, mode); }

document.addEventListener('DOMContentLoaded', () => {
  window.storeApp = new StoreApp();
  window.storeApp.init();
});
