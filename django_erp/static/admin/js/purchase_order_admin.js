// django_erp/static/admin/js/purchase_order_admin.js

console.log("🔴 SCRIPT DE COMPRAS CARGADO - CON ERP_CONFIG Y PAGOS");

// ✅ Función para obtener la tasa de IVA desde ERP_CONFIG
function getTaxRate() {
    if (window.ERP_CONFIG && window.ERP_CONFIG.tax_rate) {
        var rate = parseFloat(window.ERP_CONFIG.tax_rate);
        if (!isNaN(rate) && rate > 0) {
            console.log("   ✅ IVA obtenido de ERP_CONFIG:", rate);
            return rate;
        }
    }
    console.warn("⚠️ ERP_CONFIG no disponible o sin tax_rate, usando 16% por defecto");
    return 16;
}

// ✅ Función para obtener la tasa de cambio
function getExchangeRate() {
    if (window.ERP_CONFIG && window.ERP_CONFIG.exchange_rate > 0) {
        console.log("   ✅ Tasa obtenida de ERP_CONFIG:", window.ERP_CONFIG.exchange_rate);
        return window.ERP_CONFIG.exchange_rate;
    }
    
    var rate = 0;
    var rateField = document.getElementById('id_rate_display');
    if (rateField) {
        var rateText = rateField.value || '';
        var rateMatch = rateText.match(/Bs\.\s*(\d+\.?\d*)/);
        if (rateMatch) {
            rate = parseFloat(rateMatch[1]);
        }
    }
    if (rate === 0 || isNaN(rate)) {
        rate = 40.00;
    }
    return rate;
}

// ✅ Función para formatear números con 2 decimales
function formatNumber(value) {
    if (value === undefined || value === null || isNaN(value)) {
        return '0.00';
    }
    let num = parseFloat(value);
    return num.toFixed(2);
}

// ✅ Función para recalcular todos los totales de la orden de compra
function recalculateOrderTotals() {
    console.log("📊 RECALCULANDO TOTALES DE COMPRA");
    var subtotal = 0;
    var rows = document.querySelectorAll('tr.form-row');
    
    rows.forEach(function(row) {
        // ✅ Saltar filas de pagos (tienen select de método)
        if (row.querySelector('select[name$="-method"]')) {
            return;
        }
        
        var qtyInput = row.querySelector('input[name$="quantity"]');
        var priceInput = row.querySelector('input[name$="unit_price"]');
        var qty = parseFloat(qtyInput?.value) || 0;
        var price = parseFloat(priceInput?.value) || 0;
        subtotal += qty * price;
    });
    
    var taxRate = getTaxRate();
    var tax = subtotal * (taxRate / 100);
    var total = subtotal + tax;
    
    // Actualizar campos USD
    var subtotalField = document.getElementById('id_subtotal_display');
    var taxField = document.getElementById('id_tax_display');
    var totalField = document.getElementById('id_total_display');
    
    if (subtotalField) subtotalField.value = formatNumber(subtotal);
    if (taxField) taxField.value = formatNumber(tax);
    if (totalField) totalField.value = formatNumber(total);
    
    // Actualizar campos Bs.
    var rate = getExchangeRate();
    var subtotalBsField = document.getElementById('id_subtotal_bs_display');
    var taxBsField = document.getElementById('id_tax_bs_display');
    var totalBsField = document.getElementById('id_total_bs_display');
    
    if (subtotalBsField) subtotalBsField.value = formatNumber(subtotal * rate);
    if (taxBsField) taxBsField.value = formatNumber(tax * rate);
    if (totalBsField) totalBsField.value = formatNumber(total * rate);
}

// ✅ Función para actualizar subtotal de una línea
function updateLineSubtotal(row) {
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    
    if (!qtyInput || !priceInput) return;
    
    var qty = parseFloat(qtyInput.value) || 0;
    var price = parseFloat(priceInput.value) || 0;
    var subtotal = qty * price;
    
    var subtotalField = row.querySelector('.field-subtotal');
    if (subtotalField) {
        subtotalField.textContent = formatNumber(subtotal);
    }
    
    var subtotalInput = row.querySelector('input[name$="subtotal"]');
    if (subtotalInput) {
        subtotalInput.value = formatNumber(subtotal);
    }
}

// ✅ NUEVO: Configurar conversión de pagos (IDÉNTICO a ventas)
function setupPaymentConversion(row) {
    if (!row) {
        var paymentRows = document.querySelectorAll('tr.form-row');
        paymentRows.forEach(function(r) {
            if (r.querySelector('select[name$="-method"]')) {
                setupPaymentConversion(r);
            }
        });
        return;
    }
    
    var currencySelect = row.querySelector('select[name$="-currency"]');
    var amountInput = row.querySelector('input[name$="-amount"]');
    var amountUsdDisplay = row.querySelector('.field-amount_usd_display');
    var amountUsdInput = row.querySelector('input[name$="-amount_usd"]');
    
    if (!currencySelect || !amountInput) return;
    
    function updateConversion() {
        var selectedOption = currencySelect.options[currencySelect.selectedIndex];
        var currencyText = selectedOption ? selectedOption.text : 'USD';
        var currencyCode = currencyText.split(' - ')[0] || currencyText;
        var amount = parseFloat(amountInput.value) || 0;
        
        var usdAmount = 0;
        
        if (currencyCode === 'USD') {
            usdAmount = amount;
        } else {
            var rate = getExchangeRate();
            if (rate > 0) {
                usdAmount = amount / rate;
            } else {
                usdAmount = amount;
            }
        }
        
        usdAmount = Math.round(usdAmount * 100) / 100;
        
        if (amountUsdDisplay) {
            amountUsdDisplay.textContent = '$ ' + usdAmount.toFixed(2);
        }
        
        if (amountUsdInput) {
            amountUsdInput.value = usdAmount.toFixed(2);
        }
    }
    
    currencySelect.addEventListener('change', updateConversion);
    amountInput.addEventListener('input', updateConversion);
    amountInput.addEventListener('change', updateConversion);
    
    // ✅ Forzar actualización inicial
    setTimeout(updateConversion, 100);
}

// ✅ Función para obtener precio del producto
function fetchProductDetails(productId, row) {
    if (!productId || productId === '') return;
    if (!row) return;
    
    console.log("🔴 Solicitando datos para producto:", productId);
    
    fetch('/admin/purchasing/get-product-price/?product_id=' + productId)
        .then(response => response.json())
        .then(data => {
            console.log("   Datos recibidos:", data);
            
            var priceInput = row.querySelector('input[name$="unit_price"]');
            if (priceInput) {
                priceInput.value = data.unit_price;
                priceInput.removeAttribute('readonly');
                priceInput.style.backgroundColor = '#ffffff';
                priceInput.style.cursor = 'text';
                console.log("   ✅ Precio asignado:", data.unit_price);
            }
            
            var locationSelect = row.querySelector('select[name$="location"]');
            if (locationSelect && data.location_id) {
                for (var i = 0; i < locationSelect.options.length; i++) {
                    if (locationSelect.options[i].value == data.location_id) {
                        locationSelect.value = data.location_id;
                        console.log("   ✅ Ubicación sugerida:", data.location_code);
                        break;
                    }
                }
                locationSelect.disabled = false;
                locationSelect.style.backgroundColor = '#ffffff';
                locationSelect.style.cursor = 'pointer';
            }
            
            updateLineSubtotal(row);
            recalculateOrderTotals();
        })
        .catch(error => console.error("Error:", error));
}

// ✅ Configurar una fila (línea de producto O pago)
function setupRow(row) {
    // ✅ Si es una fila de pago, configurar conversión
    if (row.querySelector('select[name$="-method"]')) {
        setupPaymentConversion(row);
        return;
    }
    
    // ✅ Si es una fila de producto
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    var select = row.querySelector('select[id$="-product"]');
    
    if (priceInput) {
        priceInput.removeAttribute('readonly');
        priceInput.style.backgroundColor = '#ffffff';
        priceInput.style.cursor = 'text';
    }
    
    if (qtyInput) {
        qtyInput.addEventListener('change', function() {
            console.log("🔴 Cambio en cantidad:", this.value);
            updateLineSubtotal(row);
            recalculateOrderTotals();
        });
        qtyInput.addEventListener('keyup', function() {
            updateLineSubtotal(row);
            recalculateOrderTotals();
        });
    }
    
    if (priceInput) {
        priceInput.addEventListener('change', function() {
            console.log("🔴 Cambio en precio:", this.value);
            updateLineSubtotal(row);
            recalculateOrderTotals();
        });
        priceInput.addEventListener('keyup', function() {
            updateLineSubtotal(row);
            recalculateOrderTotals();
        });
    }
    
    if (select) {
        console.log("   Select de producto encontrado");
        var $ = django.jQuery;
        
        $(select).on('select2:select', function(e) {
            var productId = e.params.data.id;
            console.log("🔴 Producto seleccionado (select2):", productId);
            if (productId) {
                this.value = productId;
                fetchProductDetails(productId, row);
            }
        });
        
        select.addEventListener('change', function() {
            var productId = this.value;
            console.log("🔴 Producto seleccionado (change):", productId);
            if (productId) {
                fetchProductDetails(productId, row);
            }
        });
    }
}

// ✅ Configurar todas las filas
function setupAllRows() {
    console.log("🔴 Configurando todas las filas de compra...");
    var rows = document.querySelectorAll('tr.form-row');
    console.log("   Filas encontradas:", rows.length);
    rows.forEach(function(row, index) {
        if (!row._hasSetup) {
            row._hasSetup = true;
            console.log(`   Configurando fila ${index}`);
            setupRow(row);
        }
    });
    recalculateOrderTotals();
}

// ✅ Detectar nuevas líneas
document.addEventListener('click', function(e) {
    var addButton = e.target.closest('.add-row a') || e.target.closest('.add-row');
    if (addButton) {
        console.log("🔴 Botón 'Agregar' clickeado");
        setTimeout(function() {
            var rows = document.querySelectorAll('tr.form-row');
            rows.forEach(function(row) {
                if (!row._hasSetup) {
                    row._hasSetup = true;
                    setupRow(row);
                }
            });
            recalculateOrderTotals();
        }, 300);
    }
});

// ✅ Inicializar
function initialize() {
    console.log("🔴 INICIALIZANDO MÓDULO DE COMPRAS...");
    setupAllRows();
    console.log("✅ Inicialización completada");
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

setTimeout(initialize, 500);
setTimeout(initialize, 1000);
setTimeout(initialize, 2000);

console.log("✅ Script de compras cargado - CON ERP_CONFIG Y PAGOS");