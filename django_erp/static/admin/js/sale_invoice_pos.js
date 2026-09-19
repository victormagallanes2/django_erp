/* static/admin/js/sale_invoice_pos.js */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        const container = document.querySelector('.pos-container');
        if (!container) return;

        // Mover modal al body
        const modalEl = document.getElementById('pos-customer-modal');
        if (modalEl && modalEl.parentElement !== document.body) {
            document.body.appendChild(modalEl);
        }

        // ============================================================
        // REFERENCIAS GLOBALES
        // ============================================================
        const SEARCH_URL = container.dataset.searchUrl;
        const CHECKOUT_URL = container.dataset.checkoutUrl;
        const CUSTOMER_SEARCH_URL = container.dataset.customerSearchUrl;
        const SALESPERSONS_URL = container.dataset.salespersonsUrl || '';
        const REQUIRE_SALESPERSON = container.dataset.requireSalesperson === 'true';
        const EXCHANGE_RATE = parseFloat(container.dataset.exchangeRate) || 0;

        console.log('[POS] SEARCH_URL:', SEARCH_URL);
        console.log('[POS] CHECKOUT_URL:', CHECKOUT_URL);
        console.log('[POS] CUSTOMER_SEARCH_URL:', CUSTOMER_SEARCH_URL);
        console.log('[POS] SALESPERSONS_URL:', SALESPERSONS_URL);
        console.log('[POS] REQUIRE_SALESPERSON:', REQUIRE_SALESPERSON);

        const searchInput = document.getElementById('pos-search-input');
        const productsGrid = document.getElementById('pos-products-grid');
        const cartItems = document.getElementById('pos-cart-items');
        const cartEmpty = document.getElementById('pos-cart-empty');

        const customerHidden = document.getElementById('pos-customer');
        const customerInput = document.getElementById('pos-customer-input');
        const customerResults = document.getElementById('pos-customer-results');
        const customerLupaBtn = document.getElementById('pos-customer-lupa-btn');

        const salespersonSelect = document.getElementById('pos-salesperson');
        const salespersonBar = document.getElementById('pos-salesperson-bar');

        console.log('[POS] customerInput:', customerInput);
        console.log('[POS] customerResults:', customerResults);
        console.log('[POS] customerLupaBtn:', customerLupaBtn);
        console.log('[POS] salespersonSelect:', salespersonSelect);

        const paymentButtons = document.querySelectorAll('.pos-payment-btn');
        const paymentMethodInput = document.getElementById('pos-payment-method-id');
        const subtotalEl = document.getElementById('pos-subtotal');
        const taxEl = document.getElementById('pos-tax');
        const totalEl = document.getElementById('pos-total');
        const totalBsEl = document.getElementById('pos-total-bs');
        const checkoutBtn = document.getElementById('pos-checkout-btn');
        const clearBtn = document.getElementById('pos-clear-btn');
        const successModal = document.getElementById('pos-success-modal');

        let cart = [];
        let productsCache = [];
        let searchTimeout = null;
        let customerTimeout = null;

        // ============================================================
        // UTILIDADES
        // ============================================================
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        function escapeHtml(str) {
            if (str === null || str === undefined) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function formatMoney(n) {
            return '$ ' + parseFloat(n).toFixed(2);
        }

        // ============================================================
        // AUTOCOMPLETE DE CLIENTE
        // ============================================================
        function searchCustomers(q) {
            if (!CUSTOMER_SEARCH_URL) {
                console.warn('[POS] CUSTOMER_SEARCH_URL no está definida');
                return;
            }
            const url = CUSTOMER_SEARCH_URL + '?q=' + encodeURIComponent(q || '');
            console.log('[POS] Buscando clientes en:', url);

            fetch(url)
                .then(r => r.json())
                .then(data => {
                    console.log('[POS] Resultados:', data);
                    renderCustomerResults(data.results || []);
                })
                .catch(err => console.error('[POS] Error buscando clientes:', err));
        }

        function renderCustomerResults(results) {
            if (!customerResults) return;

            if (results.length === 0) {
                customerResults.innerHTML =
                    '<div class="pos-customer-result-empty">Sin resultados</div>';
                customerResults.classList.add('open');
                return;
            }
            customerResults.innerHTML = results.map(c => (
                '<div class="pos-customer-result-item" ' +
                     'data-id="' + c.id + '" ' +
                     'data-text="' + escapeHtml(c.text) + '">' +
                    '<span class="r-name">' + escapeHtml(c.name) + '</span>' +
                    '<span class="r-tax">' + escapeHtml(c.tax_id) + '</span>' +
                '</div>'
            )).join('');
            customerResults.classList.add('open');
        }

        function closeCustomerResults() {
            if (customerResults) {
                customerResults.classList.remove('open');
                customerResults.innerHTML = '';
            }
        }

        function selectCustomer(id, text) {
            if (customerHidden) customerHidden.value = id;
            if (customerInput) customerInput.value = text;
            closeCustomerResults();
            updateCheckoutButton();
        }

        // Evento: clic en la lupa
        if (customerLupaBtn) {
            customerLupaBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('[POS] Lupa clickeada');
                searchCustomers('');
                if (customerInput) customerInput.focus();
            });
        } else {
            console.warn('[POS] No se encontró el botón de lupa (#pos-customer-lupa-btn)');
        }

        // Evento: clic en el input → mostrar todos
        if (customerInput) {
            customerInput.addEventListener('focus', function () {
                console.log('[POS] Input de cliente enfocado');
                searchCustomers(this.value.trim());
            });

            customerInput.addEventListener('input', function () {
                clearTimeout(customerTimeout);
                const q = this.value.trim();
                if (q.length === 0) {
                    searchCustomers('');
                    return;
                }
                if (q.length < 2) {
                    closeCustomerResults();
                    if (customerHidden) customerHidden.value = '';
                    updateCheckoutButton();
                    return;
                }
                customerTimeout = setTimeout(() => searchCustomers(q), 250);
            });

            customerInput.addEventListener('keydown', function (e) {
                if (e.key === 'Escape') {
                    closeCustomerResults();
                }
            });
        }

        // Evento: clic en un resultado
        if (customerResults) {
            customerResults.addEventListener('click', function (e) {
                const item = e.target.closest('.pos-customer-result-item');
                if (!item) return;
                console.log('[POS] Cliente seleccionado:', item.dataset.id);
                selectCustomer(item.dataset.id, item.dataset.text);
            });
        }

        // Cerrar resultados al hacer clic fuera
        document.addEventListener('click', function (e) {
            if (!e.target.closest('.pos-customer-autocomplete')) {
                closeCustomerResults();
            }
        });

        // ============================================================
        // SELECTOR DE VENDEDOR (COMISIÓN)
        // ============================================================
        function loadSalespersons() {
            if (!SALESPERSONS_URL || !salespersonSelect) return;

            fetch(SALESPERSONS_URL)
                .then(r => r.json())
                .then(data => {
                    const results = data.results || [];
                    salespersonSelect.innerHTML =
                        '<option value="">— Selecciona un empleado —</option>' +
                        results.map(e =>
                            '<option value="' + e.id + '">' +
                                escapeHtml(e.text) +
                                (e.position ? ' — ' + escapeHtml(e.position) : '') +
                            '</option>'
                        ).join('');
                    console.log('[POS] Vendedores cargados:', results.length);
                })
                .catch(err => console.error('[POS] Error cargando vendedores:', err));
        }

        if (salespersonSelect) {
            salespersonSelect.addEventListener('change', function () {
                console.log('[POS] Vendedor seleccionado:', this.value);
                updateCheckoutButton();
            });
        }

        // ============================================================
        // BÚSQUEDA DE PRODUCTOS
        // ============================================================
        if (searchInput) {
            searchInput.addEventListener('input', function () {
                clearTimeout(searchTimeout);
                const q = this.value.trim();
                if (q.length === 0) {
                    doSearch('');
                    return;
                }
                searchTimeout = setTimeout(() => doSearch(q), 250);
            });

            searchInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const firstCard = productsGrid.querySelector('.pos-product-card');
                    if (firstCard) {
                        const idx = parseInt(firstCard.dataset.productIndex);
                        if (!isNaN(idx) && productsCache[idx]) {
                            addToCart(productsCache[idx]);
                            searchInput.value = '';
                            doSearch('');
                        }
                    }
                }
                if (e.key === 'Escape') {
                    searchInput.value = '';
                    doSearch('');
                }
            });
        }

        function doSearch(q) {
            fetch(SEARCH_URL + '?q=' + encodeURIComponent(q || ''))
                .then(r => r.json())
                .then(data => renderProductsGrid(data.results || []))
                .catch(err => console.error('Error buscando:', err));
        }

        function renderProductsGrid(results) {
            if (!productsGrid) return;

            productsCache = results;

            if (results.length === 0) {
                productsGrid.innerHTML =
                    '<div class="pos-products-empty">' +
                    '<div class="pos-products-empty-icon">🔍</div>' +
                    '<p>No se encontraron productos</p>' +
                    '</div>';
                return;
            }

            productsGrid.innerHTML = results.map((p, idx) => {
                const stockClass = p.stock <= 0 ? 'out' : (p.stock < 5 ? 'low' : '');
                const stockLabel = p.is_service ? 'Servicio' : ('Stock: ' + p.stock);

                const imageHtml = p.image_url
                    ? '<img src="' + escapeHtml(p.image_url) + '" alt="' + escapeHtml(p.name) + '" class="card-image" loading="lazy">'
                    : '<div class="card-image-placeholder">📦</div>';

                return (
                    '<div class="pos-product-card" data-product-index="' + idx + '">' +
                        '<div class="card-image-wrap">' + imageHtml + '</div>' +
                        '<div class="card-code">' + escapeHtml(p.code) + '</div>' +
                        '<div class="card-name">' + escapeHtml(p.name) + '</div>' +
                        '<div class="card-footer">' +
                            '<span class="card-price">' + formatMoney(p.price_usd) + '</span>' +
                            '<span class="card-stock ' + stockClass + '">' + stockLabel + '</span>' +
                        '</div>' +
                    '</div>'
                );
            }).join('');
        }

        if (productsGrid) {
            productsGrid.addEventListener('click', function (e) {
                const card = e.target.closest('.pos-product-card');
                if (!card) return;
                const idx = parseInt(card.dataset.productIndex);
                if (isNaN(idx) || !productsCache[idx]) return;
                addToCart(productsCache[idx]);
            });
        }

        // ============================================================
        // CARRITO
        // ============================================================
        function addToCart(product) {
            const existing = cart.find(x => x.product_id === product.id);
            if (existing) {
                existing.quantity += 1;
            } else {
                cart.push({
                    product_id: product.id,
                    code: product.code,
                    name: product.name,
                    unit_price: product.price_usd,
                    quantity: 1,
                    stock: product.stock,
                    location_id: product.location_id,
                    is_service: product.is_service,
                });
            }
            renderCart();
        }

        function removeFromCart(index) {
            cart.splice(index, 1);
            renderCart();
        }

        function updateQuantity(index, qty) {
            qty = parseInt(qty) || 1;
            if (qty < 1) qty = 1;
            cart[index].quantity = qty;
            renderCart();
        }

        function renderCart() {
            if (!cartItems) return;

            if (cart.length === 0) {
                cartItems.innerHTML = '';
                if (cartEmpty) cartEmpty.style.display = 'block';
            } else {
                if (cartEmpty) cartEmpty.style.display = 'none';
                cartItems.innerHTML = cart.map((item, i) => {
                    const subtotal = item.quantity * item.unit_price;
                    const stockWarning = (!item.is_service && item.quantity > item.stock)
                        ? ' <span style="color:#dc2626;font-weight:700;">⚠</span>' : '';
                    return (
                        '<div class="pos-cart-item">' +
                            '<div class="pos-cart-item-header">' +
                                '<div class="pos-cart-item-name">' + escapeHtml(item.name) + stockWarning + '</div>' +
                                '<button type="button" class="pos-cart-item-remove" data-index="' + i + '">✕</button>' +
                            '</div>' +
                            '<div class="pos-cart-item-body">' +
                                '<div class="pos-cart-item-qty">' +
                                    '<button type="button" class="qty-dec" data-index="' + i + '">−</button>' +
                                    '<input type="number" class="qty-input" min="1" value="' + item.quantity + '" data-index="' + i + '">' +
                                    '<button type="button" class="qty-inc" data-index="' + i + '">+</button>' +
                                '</div>' +
                                '<div class="pos-cart-item-subtotal">' + formatMoney(subtotal) + '</div>' +
                            '</div>' +
                        '</div>'
                    );
                }).join('');
            }
            recalcTotals();
            updateCheckoutButton();
        }

        if (cartItems) {
            cartItems.addEventListener('input', function (e) {
                if (e.target.classList.contains('qty-input')) {
                    const idx = parseInt(e.target.dataset.index);
                    updateQuantity(idx, e.target.value);
                }
            });

            cartItems.addEventListener('click', function (e) {
                const idx = parseInt(e.target.dataset.index);

                if (e.target.classList.contains('pos-cart-item-remove')) {
                    removeFromCart(idx);
                } else if (e.target.classList.contains('qty-inc')) {
                    updateQuantity(idx, cart[idx].quantity + 1);
                } else if (e.target.classList.contains('qty-dec')) {
                    updateQuantity(idx, cart[idx].quantity - 1);
                }
            });
        }

        // ============================================================
        // TOTALES
        // ============================================================
        function recalcTotals() {
            let subtotal = 0;
            cart.forEach(item => {
                subtotal += item.quantity * item.unit_price;
            });
            const taxRate = 16;
            const tax = subtotal * (taxRate / 100);
            const total = subtotal + tax;
            const totalBs = total * EXCHANGE_RATE;

            if (subtotalEl) subtotalEl.textContent = formatMoney(subtotal);
            if (taxEl) taxEl.textContent = formatMoney(tax);
            if (totalEl) totalEl.textContent = formatMoney(total);
            if (totalBsEl) totalBsEl.textContent = 'Bs. ' + totalBs.toFixed(2);
        }

        // ============================================================
        // MÉTODOS DE PAGO
        // ============================================================
        paymentButtons.forEach(btn => {
            btn.addEventListener('click', function () {
                paymentButtons.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                paymentMethodInput.value = this.dataset.methodId;
                updateCheckoutButton();
            });
        });

        // ============================================================
        // ESTADO DEL BOTÓN COBRAR
        // ============================================================
        function updateCheckoutButton() {
            if (!checkoutBtn) return;

            const customerValue    = customerHidden ? String(customerHidden.value || '').trim() : '';
            const paymentValue     = paymentMethodInput ? String(paymentMethodInput.value || '').trim() : '';
            const salespersonValue = salespersonSelect ? String(salespersonSelect.value || '').trim() : '';

            const hasCustomer    = customerValue !== '';
            const hasPayment     = paymentValue !== '';
            const hasItems       = Array.isArray(cart) && cart.length > 0;
            const hasSalesperson = !REQUIRE_SALESPERSON || salespersonValue !== '';

            const shouldEnable = hasCustomer && hasPayment && hasItems && hasSalesperson;
            checkoutBtn.disabled = !shouldEnable;

            const missing = [];
            if (!hasItems)        missing.push('agregar productos');
            if (!hasCustomer)     missing.push('seleccionar cliente');
            if (!hasPayment)      missing.push('seleccionar método de pago');
            if (!hasSalesperson)  missing.push('seleccionar vendedor');
            checkoutBtn.title = missing.length
                ? 'Falta: ' + missing.join(', ')
                : 'Procesar venta';
        }

        // ============================================================
        // LIMPIAR
        // ============================================================
        if (clearBtn) {
            clearBtn.addEventListener('click', function () {
                if (cart.length === 0) return;
                if (!confirm('¿Vaciar el carrito?')) return;
                cart = [];
                renderCart();
                if (customerHidden) customerHidden.value = '';
                if (customerInput) customerInput.value = '';
                if (paymentMethodInput) paymentMethodInput.value = '';
                if (salespersonSelect) salespersonSelect.value = '';
                paymentButtons.forEach(b => b.classList.remove('active'));
                updateCheckoutButton();
                if (searchInput) {
                    searchInput.value = '';
                    searchInput.focus();
                }
                doSearch('');
            });
        }

        // ============================================================
        // CHECKOUT
        // ============================================================
        if (checkoutBtn) {
            checkoutBtn.addEventListener('click', function () {
                if (checkoutBtn.disabled) return;

                const payload = {
                    customer_id: parseInt(customerHidden.value),
                    payment_method_id: parseInt(paymentMethodInput.value),
                    salesperson_id: (salespersonSelect && salespersonSelect.value)
                        ? parseInt(salespersonSelect.value)
                        : null,
                    note: '',
                    lines: cart.map(item => ({
                        product_id: item.product_id,
                        quantity: item.quantity,
                        unit_price: item.unit_price,
                        location_id: item.location_id,
                    })),
                };

                checkoutBtn.disabled = true;
                checkoutBtn.textContent = '⏳ Procesando...';

                fetch(CHECKOUT_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(payload),
                })
                    .then(r => r.json().then(data => ({ ok: r.ok, data })))
                    .then(({ ok, data }) => {
                        if (!ok || data.error) {
                            alert('❌ ' + (data.error || 'Error al procesar la venta'));
                            resetCheckoutButton();
                            return;
                        }
                        showSuccessModal(data);
                    })
                    .catch(err => {
                        console.error(err);
                        alert('❌ Error de red al procesar la venta');
                        resetCheckoutButton();
                    });
            });
        }

        function resetCheckoutButton() {
            if (!checkoutBtn) return;
            checkoutBtn.textContent = '✅ Cobrar';
            updateCheckoutButton();
        }

        function showSuccessModal(data) {
            if (!successModal) return;
            document.getElementById('pos-success-number').textContent = data.invoice_number;
            document.getElementById('pos-success-total').textContent = formatMoney(data.total);
            const printBtn = document.getElementById('pos-print-btn');
            if (printBtn) printBtn.href = data.print_url;
            successModal.style.display = 'flex';
        }

        const newSaleBtn = document.getElementById('pos-new-sale-btn');
        if (newSaleBtn) {
            newSaleBtn.addEventListener('click', function () {
                successModal.style.display = 'none';
                cart = [];
                renderCart();
                if (customerHidden) customerHidden.value = '';
                if (customerInput) customerInput.value = '';
                if (paymentMethodInput) paymentMethodInput.value = '';
                if (salespersonSelect) salespersonSelect.value = '';
                paymentButtons.forEach(b => b.classList.remove('active'));
                resetCheckoutButton();
                if (searchInput) {
                    searchInput.value = '';
                    searchInput.focus();
                }
                doSearch('');
            });
        }

        // ============================================================
        // MODAL: AGREGAR CLIENTE
        // ============================================================
        const customerModal = document.getElementById('pos-customer-modal');
        const customerModalBody = document.getElementById('pos-customer-modal-body');
        const openCustomerModalBtn = document.getElementById('pos-open-customer-modal-btn');
        const closeCustomerModalBtn = document.getElementById('pos-customer-modal-close-btn');

        function closeCustomerModal() {
            if (customerModal) customerModal.style.display = 'none';
            if (customerModalBody) customerModalBody.innerHTML = '';
        }

        if (closeCustomerModalBtn) {
            closeCustomerModalBtn.addEventListener('click', closeCustomerModal);
        }

        if (openCustomerModalBtn && customerModal && customerModalBody) {
            openCustomerModalBtn.addEventListener('click', function () {
                const url = this.dataset.customerAddUrl;

                customerModalBody.innerHTML = '<div style="text-align:center;padding:2rem;color:#6b7280;">Cargando...</div>';
                customerModal.style.display = 'flex';

                fetch(url, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                })
                    .then(r => r.text())
                    .then(html => {
                        customerModalBody.innerHTML = html;
                        const form = customerModalBody.querySelector('form');
                        if (form) bindCustomerFormSubmit(form);
                    })
                    .catch(err => {
                        console.error('Error cargando formulario:', err);
                        customerModalBody.innerHTML = '<p style="color:red;">Error cargando formulario</p>';
                    });
            });
        }

        function bindCustomerFormSubmit(form) {
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                e.stopPropagation();

                const formData = new FormData(form);
                const action = form.action || window.location.href;

                fetch(action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                })
                    .then(r => {
                        const contentType = r.headers.get('content-type') || '';
                        if (contentType.includes('application/json')) {
                            return r.json().then(data => ({ isJson: true, data }));
                        }
                        return r.text().then(html => ({ isJson: false, data: html }));
                    })
                    .then(({ isJson, data }) => {
                        if (isJson && data.success) {
                            const text = data.customer_tax_id
                                ? `${data.customer_name} (${data.customer_tax_id})`
                                : data.customer_name;
                            selectCustomer(String(data.customer_id), text);
                            closeCustomerModal();
                        } else if (!isJson) {
                            customerModalBody.innerHTML = data;
                            const newForm = customerModalBody.querySelector('form');
                            if (newForm) bindCustomerFormSubmit(newForm);
                        } else {
                            alert('Error: ' + (data.error || 'No se pudo guardar el cliente'));
                        }
                    })
                    .catch(err => {
                        console.error('Error guardando cliente:', err);
                        alert('Error al guardar el cliente');
                    });
            });
        }

        if (customerModal) {
            customerModal.addEventListener('click', function (e) {
                if (e.target === this) closeCustomerModal();
            });
        }

        // ============================================================
        // ATAJOS DE TECLADO
        // ============================================================
        document.addEventListener('keydown', function (e) {
            if (e.key === 'F2') {
                e.preventDefault();
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }
            if (e.key === 'F12') {
                e.preventDefault();
                if (checkoutBtn && !checkoutBtn.disabled) checkoutBtn.click();
            }
            if (e.key === 'Escape') {
                if (customerModal && customerModal.style.display === 'flex') {
                    closeCustomerModal();
                }
            }
        });

        // ============================================================
        // INICIALIZACIÓN
        // ============================================================
        renderCart();
        updateCheckoutButton();
        loadSalespersons();
        doSearch('');

        console.log('[POS] Inicializado correctamente');
    });
})();