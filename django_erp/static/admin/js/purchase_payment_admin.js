// django_erp/static/admin/js/purchase_payment_admin.js

console.log("🔴 SCRIPT DE PAGOS DE COMPRAS CARGADO");

// ✅ Función para obtener la tasa de cambio desde ERP_CONFIG
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
    console.log("   Tasa obtenida de rate_display:", rate);
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

// ✅ Función para obtener el símbolo de una moneda
function getCurrencySymbol(currencyCode) {
    var symbols = {
        'USD': '$',
        'BS': 'Bs.',
        'EUR': '€'
    };
    return symbols[currencyCode] || currencyCode;
}

// ✅ Función principal: Configurar conversión de moneda en pagos
function setupPaymentConversion(row) {
    if (!row) {
        // ✅ Buscar todas las filas de pagos
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
    
    if (!currencySelect || !amountInput) {
        console.log("   ⚠️ No se encontraron campos de moneda o monto en esta fila");
        return;
    }
    
    console.log("🔴 Configurando conversión de pago");
    console.log("   Moneda:", currencySelect.id);
    console.log("   Monto:", amountInput.id);
    
    function updateConversion() {
        var selectedOption = currencySelect.options[currencySelect.selectedIndex];
        var currencyText = selectedOption ? selectedOption.text : 'USD';
        var currencyCode = currencyText.split(' - ')[0] || currencyText;
        var amount = parseFloat(amountInput.value) || 0;
        
        console.log("   Actualizando conversión:", amount, currencyCode);
        
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
        
        // ✅ Redondear a 2 decimales
        usdAmount = Math.round(usdAmount * 100) / 100;
        
        console.log("   USD calculado:", usdAmount);
        
        // ✅ Actualizar display del monto en USD
        if (amountUsdDisplay) {
            amountUsdDisplay.textContent = '$ ' + usdAmount.toFixed(2);
            console.log("   ✅ Display USD actualizado:", amountUsdDisplay.textContent);
        }
        
        // ✅ Actualizar campo oculto (si existe)
        if (amountUsdInput) {
            amountUsdInput.value = usdAmount.toFixed(2);
            console.log("   ✅ Input USD actualizado:", amountUsdInput.value);
        }
        
        // ✅ También actualizar el campo amount_usd si está visible
        var amountUsdField = row.querySelector('input[name$="amount_usd"]');
        if (amountUsdField && amountUsdField !== amountUsdInput) {
            amountUsdField.value = usdAmount.toFixed(2);
            console.log("   ✅ Campo amount_usd actualizado:", amountUsdField.value);
        }
    }
    
    // ✅ Eventos para actualizar conversión
    currencySelect.addEventListener('change', function() {
        console.log("🔴 Cambio de moneda:", this.value);
        updateConversion();
    });
    
    amountInput.addEventListener('input', function() {
        updateConversion();
    });
    
    amountInput.addEventListener('change', function() {
        updateConversion();
    });
    
    // ✅ Forzar actualización inicial
    setTimeout(updateConversion, 100);
}

// ✅ Configurar todas las filas de pagos
function setupAllPaymentRows() {
    console.log("🔴 Configurando todas las filas de pagos...");
    var rows = document.querySelectorAll('tr.form-row');
    var paymentCount = 0;
    
    rows.forEach(function(row, index) {
        if (row.querySelector('select[name$="-method"]')) {
            paymentCount++;
            if (!row._hasPaymentSetup) {
                row._hasPaymentSetup = true;
                console.log(`   Configurando fila de pago ${index}`);
                setupPaymentConversion(row);
            }
        }
    });
    
    console.log(`✅ ${paymentCount} filas de pago configuradas`);
}

// ✅ Detectar nuevas filas de pago (cuando se agrega un inline)
document.addEventListener('click', function(e) {
    var addButton = e.target.closest('.add-row a') || e.target.closest('.add-row');
    if (addButton) {
        console.log("🔴 Botón 'Agregar' clickeado - esperando nueva fila...");
        setTimeout(function() {
            var rows = document.querySelectorAll('tr.form-row');
            rows.forEach(function(row) {
                if (row.querySelector('select[name$="-method"]') && !row._hasPaymentSetup) {
                    row._hasPaymentSetup = true;
                    console.log("🔴 Configurando nueva fila de pago");
                    setupPaymentConversion(row);
                }
            });
        }, 300);
        // ✅ Segundo intento por si el DOM tarda más
        setTimeout(function() {
            var rows = document.querySelectorAll('tr.form-row');
            rows.forEach(function(row) {
                if (row.querySelector('select[name$="-method"]') && !row._hasPaymentSetup) {
                    row._hasPaymentSetup = true;
                    console.log("🔴 Configurando nueva fila de pago (segundo intento)");
                    setupPaymentConversion(row);
                }
            });
        }, 600);
    }
});

// ✅ También detectar eventos de formset:added (de Unfold)
document.addEventListener('formset:added', function(event) {
    console.log("🔴 Evento formset:added detectado");
    setTimeout(function() {
        var target = event.target || document;
        var rows = target.querySelectorAll('tr.form-row');
        rows.forEach(function(row) {
            if (row.querySelector('select[name$="-method"]') && !row._hasPaymentSetup) {
                row._hasPaymentSetup = true;
                console.log("🔴 Configurando nueva fila de pago (formset:added)");
                setupPaymentConversion(row);
            }
        });
    }, 100);
});

// ✅ Inicializar cuando el DOM esté listo
function initialize() {
    console.log("🔴 INICIALIZANDO PAGOS DE COMPRAS...");
    setupAllPaymentRows();
    console.log("✅ Inicialización de pagos completada");
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

// ✅ Reinicializar después de que cargue todo
setTimeout(initialize, 500);
setTimeout(initialize, 1000);
setTimeout(initialize, 2000);

console.log("✅ Script de pagos de compras cargado");