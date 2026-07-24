// django_erp/static/admin/js/invoice_admin.js

console.log("🔴 SCRIPT DE FACTURACIÓN CARGADO");

// ✅ Función para formatear números con 2 decimales
function formatNumber(value) {
    if (value === undefined || value === null || isNaN(value)) {
        return '0.00';
    }
    let num = parseFloat(value);
    return num.toFixed(2);
}

// ✅ Función para formatear moneda con separadores
function formatCurrency(value, currency) {
    let num = parseFloat(value);
    if (isNaN(num)) return '0.00';
    num = Math.round(num * 100) / 100;
    let formatted = num.toFixed(2);
    let parts = formatted.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    if (currency === 'BS') {
        return 'Bs. ' + parts.join(',');
    }
    return '$ ' + parts.join(',');
}

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
        var rateMatch = rateText.match(/(\d+\.?\d*)/g);
        if (rateMatch && rateMatch.length > 0) {
            rate = parseFloat(rateMatch[rateMatch.length - 1]);
        }
    }
    if (rate === 0 || isNaN(rate)) {
        rate = 40.00;
    }
    return rate;
}

// ✅ Función para obtener datos del producto
function fetchProductData(productCode, row) {
    if (!productCode || productCode === '') return;
    if (!row) return;
    
    fetch('/admin/invoicing/get-product-price/?product_id=' + productCode)
        .then(response => response.json())
        .then(data => {
            var priceInput = row.querySelector('input[name$="unit_price"]');
            if (priceInput) {
                priceInput.value = data.unit_price;
                priceInput.setAttribute('readonly', 'readonly');
                priceInput.style.backgroundColor = '#f0f0f0';
                priceInput.style.cursor = 'not-allowed';
                priceInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            
            var nameInput = row.querySelector('input[name$="product_name"]');
            if (nameInput && data.product_name) {
                nameInput.value = data.product_name;
            }
            
            updateLineSubtotal(row);
            recalculateTotals();
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

// ✅ Función para recalcular todos los totales
function recalculateTotals() {
    var subtotal = 0;
    var rows = document.querySelectorAll('tr.form-row');
    
    rows.forEach(function(row) {
        var qtyInput = row.querySelector('input[name$="quantity"]');
        var priceInput = row.querySelector('input[name$="unit_price"]');
        
        var qty = parseFloat(qtyInput?.value) || 0;
        var price = parseFloat(priceInput?.value) || 0;
        subtotal += qty * price;
    });
    
    // ✅ Usar la tasa de IVA de la empresa
    var taxRate = getTaxRate();
    var tax = subtotal * (taxRate / 100);
    var total = subtotal + tax;
    
    var rate = getExchangeRate();
    
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
    
    var subtotalBsField = document.getElementById('id_subtotal_bs_display');
    var taxBsField = document.getElementById('id_tax_bs_display');
    var totalBsField = document.getElementById('id_total_bs_display');
    
    if (subtotalBsField) {
        var subtotalBs = subtotal * rate;
        subtotalBsField.value = formatNumber(subtotalBs);
        subtotalBsField.textContent = formatCurrency(subtotalBs, 'BS');
    }
    if (taxBsField) {
        var taxBs = tax * rate;
        taxBsField.value = formatNumber(taxBs);
        taxBsField.textContent = formatCurrency(taxBs, 'BS');
    }
    if (totalBsField) {
        var totalBs = total * rate;
        totalBsField.value = formatNumber(totalBs);
        totalBsField.textContent = formatCurrency(totalBs, 'BS');
    }
}

// ✅ Configurar eventos en una fila
function setupRow(row) {
    var codeInput = row.querySelector('input[name$="product_code"]');
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    var rowRef = row;
    
    if (codeInput) {
        codeInput.addEventListener('change', function() {
            var productCode = this.value;
            if (productCode) {
                fetchProductData(productCode, rowRef);
            }
        });
        codeInput.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') {
                var productCode = this.value;
                if (productCode) {
                    fetchProductData(productCode, rowRef);
                }
            }
        });
    }
    
    if (qtyInput) {
        qtyInput.addEventListener('change', function() {
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
        qtyInput.addEventListener('keyup', function() {
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
    }
    
    if (priceInput) {
        priceInput.addEventListener('change', function() {
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
        priceInput.addEventListener('keyup', function() {
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
    }
}

// ✅ Configurar todas las filas
function setupAllRows() {
    var rows = document.querySelectorAll('tr.form-row');
    rows.forEach(function(row, index) {
        if (!row._hasSetup) {
            row._hasSetup = true;
            setupRow(row);
        }
    });
    recalculateTotals();
}

// ✅ Detectar nuevas líneas
document.addEventListener('click', function(e) {
    var addButton = e.target.closest('.add-row a') || e.target.closest('.add-row');
    if (addButton) {
        setTimeout(function() {
            var rows = document.querySelectorAll('tr.form-row');
            rows.forEach(function(row) {
                if (!row._hasSetup) {
                    row._hasSetup = true;
                    setupRow(row);
                }
            });
            recalculateTotals();
        }, 300);
        setTimeout(function() {
            recalculateTotals();
        }, 600);
    }
});

// ✅ Inicializar
function initialize() {
    setupAllRows();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

setTimeout(initialize, 500);
setTimeout(initialize, 1000);
setTimeout(initialize, 2000);

console.log("✅ Script de facturación cargado con ERP_CONFIG");