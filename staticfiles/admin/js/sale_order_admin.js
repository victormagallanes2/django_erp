// django_erp/static/admin/js/sale_order_admin.js

console.log("🔴 SCRIPT CARGADO - VERSIÓN CON ERP_CONFIG");

// ✅ Función para formatear números con 2 decimales
function formatNumber(value) {
    if (value === undefined || value === null || isNaN(value)) {
        return '0.00';
    }
    let num = parseFloat(value);
    return num.toFixed(2);
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
    
    // Fallback: buscar en el campo rate_display
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

// ✅ Función para obtener precio y asignarlo
function fetchProductDetails(productId, row) {
    if (!productId || productId === '') return;
    if (!row) return;
    
    fetch('/admin/sales/get-product-price/?product_id=' + productId)
        .then(response => response.json())
        .then(data => {
            var priceInput = row.querySelector('input[name$="unit_price"]');
            if (!priceInput) {
                priceInput = row.querySelector('input[id*="unit_price"]');
            }
            
            if (priceInput) {
                priceInput.value = data.unit_price;
                priceInput.setAttribute('readonly', 'readonly');
                priceInput.style.backgroundColor = '#f0f0f0';
                priceInput.style.cursor = 'not-allowed';
                priceInput.dispatchEvent(new Event('change', { bubbles: true }));
            } else {
                var priceDisplay = row.querySelector('.field-unit_price');
                if (priceDisplay) {
                    var displayHtml = '';
                    if (data.rate && data.rate > 0) {
                        displayHtml = '<div><strong>$ ' + data.unit_price.toFixed(2) + '</strong></div>' +
                                     '<div style="color: #6c757d; font-size: 11px;">Bs. ' + data.price_bs.toFixed(2) + '</div>';
                    } else {
                        displayHtml = '$ ' + data.unit_price.toFixed(2);
                    }
                    priceDisplay.innerHTML = displayHtml;
                }
            }
            
            var locationSelect = row.querySelector('select[name$="location"]');
            if (locationSelect && data.location_id) {
                for (var i = 0; i < locationSelect.options.length; i++) {
                    if (locationSelect.options[i].value == data.location_id) {
                        locationSelect.value = data.location_id;
                        break;
                    }
                }
                locationSelect.disabled = true;
                locationSelect.style.backgroundColor = '#f0f0f0';
                locationSelect.style.cursor = 'not-allowed';
            }
            
            updateLineSubtotal(row);
            recalculateOrderTotals();
        })
        .catch(error => console.error("Error:", error));
}

// ✅ Función para actualizar subtotal de una línea
function updateLineSubtotal(row) {
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    
    if (!priceInput) {
        var priceDisplay = row.querySelector('.field-unit_price');
        if (priceDisplay) {
            var text = priceDisplay.textContent || '';
            var match = text.match(/\$?\s*([\d,]+\.?\d*)/);
            if (match) {
                var priceValue = parseFloat(match[1].replace(/,/g, ''));
                updateTotalsFromValues(row, qtyInput, priceValue);
                return;
            }
        }
        return;
    }
    
    if (!qtyInput) return;
    
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

function updateTotalsFromValues(row, qtyInput, priceValue) {
    var qty = parseFloat(qtyInput?.value) || 0;
    var price = priceValue || 0;
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

// ✅ Función para recalcular todos los totales de la orden
function recalculateOrderTotals() {
    var subtotal = 0;
    var rows = document.querySelectorAll('tr.form-row');
    
    rows.forEach(function(row) {
        if (row.querySelector('select[name$="-method"]')) {
            return;
        }
        
        var qtyInput = row.querySelector('input[name$="quantity"]');
        var priceInput = row.querySelector('input[name$="unit_price"]');
        
        var qty = parseFloat(qtyInput?.value) || 0;
        var price = 0;
        
        if (priceInput) {
            price = parseFloat(priceInput.value) || 0;
        } else {
            var priceDisplay = row.querySelector('.field-unit_price');
            if (priceDisplay) {
                var text = priceDisplay.textContent || '';
                var match = text.match(/\$?\s*([\d,]+\.?\d*)/);
                if (match) {
                    price = parseFloat(match[1].replace(/,/g, '')) || 0;
                }
            }
        }
        
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
    
    if (subtotalField) subtotalField.value = formatNumber(subtotal);
    if (taxField) taxField.value = formatNumber(tax);
    if (totalField) totalField.value = formatNumber(total);
    
    var subtotalBsField = document.getElementById('id_subtotal_bs_display');
    var taxBsField = document.getElementById('id_tax_bs_display');
    var totalBsField = document.getElementById('id_total_bs_display');
    
    if (subtotalBsField) {
        subtotalBsField.value = formatNumber(subtotal * rate);
    }
    if (taxBsField) {
        taxBsField.value = formatNumber(tax * rate);
    }
    if (totalBsField) {
        totalBsField.value = formatNumber(total * rate);
    }
}

// ✅ Configurar eventos para conversión de pagos
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
    
    setTimeout(updateConversion, 100);
}

// ✅ Configurar eventos
function setupRow(row) {
    if (row.querySelector('select[name$="-method"]')) {
        setupPaymentConversion(row);
        return;
    }
    
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    var select = row.querySelector('select[id$="-product"]');
    var rowRef = row;
    
    if (priceInput && !priceInput.hasAttribute('readonly')) {
        priceInput.setAttribute('readonly', 'readonly');
        priceInput.style.backgroundColor = '#f0f0f0';
        priceInput.style.cursor = 'not-allowed';
    }
    
    if (qtyInput) {
        qtyInput.addEventListener('change', function() {
            updateLineSubtotal(rowRef);
            recalculateOrderTotals();
        });
        qtyInput.addEventListener('keyup', function() {
            updateLineSubtotal(rowRef);
            recalculateOrderTotals();
        });
    }
    
    if (select) {
        var $ = django.jQuery;
        
        $(select).on('select2:select', function(e) {
            var productId = e.params.data.id;
            if (productId) {
                this.value = productId;
                fetchProductDetails(productId, rowRef);
            }
        });
        
        select.addEventListener('change', function() {
            var productId = this.value;
            if (productId) {
                fetchProductDetails(productId, rowRef);
            }
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
    recalculateOrderTotals();
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
            recalculateOrderTotals();
        }, 300);
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

console.log("✅ Script cargado - VERSIÓN FINAL CON ERP_CONFIG");