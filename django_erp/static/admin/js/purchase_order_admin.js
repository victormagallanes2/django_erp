// django_erp/static/admin/js/purchase_order_admin.js

console.log("🔴 SCRIPT DE COMPRAS CARGADO - CON ERP_CONFIG");

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

// ✅ Función para recalcular todos los totales de la orden de compra
function recalculateOrderTotals() {
    console.log("📊 RECALCULANDO TOTALES DE COMPRA");
    var subtotal = 0;
    var rows = document.querySelectorAll('tr.form-row');
    
    rows.forEach(function(row) {
        var qtyInput = row.querySelector('input[name$="quantity"]');
        var priceInput = row.querySelector('input[name$="unit_price"]');
        var qty = parseFloat(qtyInput?.value) || 0;
        var price = parseFloat(priceInput?.value) || 0;
        subtotal += qty * price;
        console.log(`   Línea: ${qty} x ${price} = ${qty * price}`);
    });
    
    // ✅ Usar la tasa de IVA desde ERP_CONFIG
    var taxRate = getTaxRate();
    var tax = subtotal * (taxRate / 100);
    var total = subtotal + tax;
    
    console.log(`   Subtotal: ${subtotal.toFixed(2)}, IVA: ${taxRate}% -> ${tax.toFixed(2)}, Total: ${total.toFixed(2)}`);
    
    // ✅ Actualizar campos de totales en USD
    var subtotalField = document.getElementById('id_subtotal_display');
    var taxField = document.getElementById('id_tax_display');
    var totalField = document.getElementById('id_total_display');
    
    if (subtotalField) {
        subtotalField.value = subtotal.toFixed(2);
        console.log(`   ✅ Subtotal USD actualizado: ${subtotal.toFixed(2)}`);
    }
    if (taxField) {
        taxField.value = tax.toFixed(2);
        console.log(`   ✅ IVA USD actualizado: ${tax.toFixed(2)}`);
    }
    if (totalField) {
        totalField.value = total.toFixed(2);
        console.log(`   ✅ Total USD actualizado: ${total.toFixed(2)}`);
    }
    
    // ✅ Actualizar campos en Bs.
    var rate = getExchangeRate();
    
    var subtotalBsField = document.getElementById('id_subtotal_bs_display');
    var taxBsField = document.getElementById('id_tax_bs_display');
    var totalBsField = document.getElementById('id_total_bs_display');
    
    if (subtotalBsField) {
        var subtotalBs = subtotal * rate;
        subtotalBsField.value = subtotalBs.toFixed(2);
        console.log(`   ✅ Subtotal Bs.: ${subtotalBs.toFixed(2)}`);
    }
    if (taxBsField) {
        var taxBs = tax * rate;
        taxBsField.value = taxBs.toFixed(2);
        console.log(`   ✅ IVA Bs.: ${taxBs.toFixed(2)}`);
    }
    if (totalBsField) {
        var totalBs = total * rate;
        totalBsField.value = totalBs.toFixed(2);
        console.log(`   ✅ Total Bs.: ${totalBs.toFixed(2)}`);
    }
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
        console.log(`   ✅ Subtotal línea: ${subtotal.toFixed(2)}`);
    }
}

// ✅ Función para obtener precio del producto (usando la URL de compras)
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
                // En compras, el precio es editable (se puede negociar)
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
                // En compras, la ubicación se puede cambiar
                locationSelect.disabled = false;
                locationSelect.style.backgroundColor = '#ffffff';
                locationSelect.style.cursor = 'pointer';
            }
            
            updateLineSubtotal(row);
            recalculateOrderTotals();
        })
        .catch(error => console.error("Error:", error));
}

// ✅ Configurar una fila
function setupRow(row) {
    console.log("🔴 Configurando fila de compra");
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    var select = row.querySelector('select[id$="-product"]');
    
    // En compras, el precio debe ser editable
    if (priceInput) {
        priceInput.removeAttribute('readonly');
        priceInput.style.backgroundColor = '#ffffff';
        priceInput.style.cursor = 'text';
    }
    
    if (qtyInput) {
        console.log("   Cantidad encontrada");
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
        console.log("   Precio encontrado");
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

console.log("✅ Script de compras cargado - CON ERP_CONFIG");