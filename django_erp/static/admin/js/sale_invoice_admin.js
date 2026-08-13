// django_erp/static/admin/js/sale_invoice_admin.js

console.log("🔴 SCRIPT DE FACTURAS DE VENTA CARGADO");

// ✅ Función para formatear números
function formatNumber(value) {
    if (value === undefined || value === null || isNaN(value)) {
        return '0.00';
    }
    let num = parseFloat(value);
    return num.toFixed(2);
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
        var rateMatch = rateText.match(/(\d+\.?\d*)/g);
        if (rateMatch && rateMatch.length > 0) {
            rate = parseFloat(rateMatch[rateMatch.length - 1]);
        }
    }
    if (rate === 0 || isNaN(rate)) {
        rate = 40.00;
    }
    console.log("   Tasa obtenida de rate_display:", rate);
    return rate;
}

// ✅ Función para obtener la tasa de IVA
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

// ✅ Función para obtener datos del producto (precio + stock)
function fetchProductData(productId, row) {
    if (!productId || productId === '') return;
    if (!row) return;
    
    console.log("🔴 Obteniendo datos para producto ID:", productId);
    
    fetch('/admin/sales/get-product-price/?product_id=' + productId)
        .then(response => response.json())
        .then(data => {
            console.log("   Datos recibidos:", data);
            
            // ✅ Actualizar precio unitario
            var priceInput = row.querySelector('input[name$="unit_price"]');
            if (priceInput) {
                priceInput.value = data.unit_price;
                priceInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            
            // ✅ Actualizar campo de stock (solo lectura)
            var stockField = row.querySelector('.field-stock_display');
            if (stockField) {
                if (data.stock !== undefined) {
                    stockField.textContent = data.stock_display || data.stock + ' unidades';
                } else {
                    stockField.textContent = 'Sin stock';
                }
            }
            
            // ✅ Actualizar subtotal
            updateLineSubtotal(row);
            recalculateInvoiceTotals();
        })
        .catch(error => console.error("Error:", error));
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
        subtotalField.textContent = subtotal.toFixed(2);
    }
    
    var subtotalInput = row.querySelector('input[name$="subtotal"]');
    if (subtotalInput) {
        subtotalInput.value = subtotal.toFixed(2);
    }
}

// ✅ Función para recalcular totales de la factura (USD y Bs.)
function recalculateInvoiceTotals() {
    var subtotal = 0;
    var rows = document.querySelectorAll('tr.form-row');
    
    rows.forEach(function(row) {
        // Saltar filas que no son de productos (como pagos)
        if (row.querySelector('select[name$="-method"]')) {
            return;
        }
        
        var qtyInput = row.querySelector('input[name$="quantity"]');
        var priceInput = row.querySelector('input[name$="unit_price"]');
        
        var qty = parseFloat(qtyInput?.value) || 0;
        var price = parseFloat(priceInput?.value) || 0;
        subtotal += qty * price;
    });
    
    // ✅ Obtener tasa de IVA
    var taxRate = getTaxRate();
    var tax = subtotal * (taxRate / 100);
    var total = subtotal + tax;
    
    // ✅ Obtener tasa de cambio
    var rate = getExchangeRate();
    
    // ✅ Actualizar campos en USD
    var subtotalField = document.getElementById('id_subtotal_display');
    var taxField = document.getElementById('id_tax_display');
    var totalField = document.getElementById('id_total_display');
    
    if (subtotalField) {
        subtotalField.value = formatNumber(subtotal);
        subtotalField.textContent = formatNumber(subtotal);
    }
    if (taxField) {
        taxField.value = formatNumber(tax);
        taxField.textContent = formatNumber(tax);
    }
    if (totalField) {
        totalField.value = formatNumber(total);
        totalField.textContent = formatNumber(total);
    }
    
    // ✅ Actualizar campos en Bs.
    var subtotalBsField = document.getElementById('id_subtotal_bs_display');
    var taxBsField = document.getElementById('id_tax_bs_display');
    var totalBsField = document.getElementById('id_total_bs_display');
    
    if (subtotalBsField) {
        var subtotalBs = subtotal * rate;
        subtotalBsField.value = formatNumber(subtotalBs);
        subtotalBsField.textContent = formatNumber(subtotalBs);
    }
    if (taxBsField) {
        var taxBs = tax * rate;
        taxBsField.value = formatNumber(taxBs);
        taxBsField.textContent = formatNumber(taxBs);
    }
    if (totalBsField) {
        var totalBs = total * rate;
        totalBsField.value = formatNumber(totalBs);
        totalBsField.textContent = formatNumber(totalBs);
    }
}

// ✅ Configurar eventos en una fila
function setupRow(row) {
    var select = row.querySelector('select[id$="-product"]');
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    var rowRef = row;
    
    // ✅ Cuando se selecciona un producto
    if (select) {
        var $ = django.jQuery;
        
        $(select).on('select2:select', function(e) {
            var productId = e.params.data.id;
            console.log("🔴 Producto seleccionado (select2):", productId);
            if (productId) {
                this.value = productId;
                fetchProductData(productId, rowRef);
            }
        });
        
        select.addEventListener('change', function() {
            var productId = this.value;
            console.log("🔴 Producto seleccionado (change):", productId);
            if (productId) {
                fetchProductData(productId, rowRef);
            }
        });
    }
    
    // ✅ Cuando cambia la cantidad
    if (qtyInput) {
        qtyInput.addEventListener('change', function() {
            updateLineSubtotal(rowRef);
            recalculateInvoiceTotals();
        });
        qtyInput.addEventListener('keyup', function() {
            updateLineSubtotal(rowRef);
            recalculateInvoiceTotals();
        });
    }
    
    // ✅ Cuando cambia el precio
    if (priceInput) {
        priceInput.addEventListener('change', function() {
            updateLineSubtotal(rowRef);
            recalculateInvoiceTotals();
        });
        priceInput.addEventListener('keyup', function() {
            updateLineSubtotal(rowRef);
            recalculateInvoiceTotals();
        });
    }
}

// ✅ Configurar todas las filas
function setupAllRows() {
    console.log("🔴 Configurando líneas de factura...");
    var rows = document.querySelectorAll('tr.form-row');
    rows.forEach(function(row, index) {
        if (!row._hasSetup) {
            row._hasSetup = true;
            setupRow(row);
        }
    });
    recalculateInvoiceTotals();
}

// ✅ Detectar nuevas líneas agregadas dinámicamente
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
            recalculateInvoiceTotals();
        }, 300);
        setTimeout(function() {
            recalculateInvoiceTotals();
        }, 600);
    }
});

// ✅ Inicializar
function initialize() {
    console.log("🔴 INICIALIZANDO FACTURAS DE VENTA...");
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

console.log("✅ Script de facturas de venta cargado");