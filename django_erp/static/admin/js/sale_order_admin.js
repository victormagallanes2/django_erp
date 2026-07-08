// django_erp/static/admin/js/sale_order_admin.js

console.log("🔴 SCRIPT CARGADO - VERSIÓN FINAL");

// ✅ Función para recalcular todos los totales de la orden
function recalculateOrderTotals() {
    console.log("📊 RECALCULANDO TOTALES");
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
    
    var taxRate = 19;
    var tax = subtotal * (taxRate / 100);
    var total = subtotal + tax;
    
    console.log(`   Subtotal: ${subtotal.toFixed(2)}, IVA: ${tax.toFixed(2)}, Total: ${total.toFixed(2)}`);
    
    // ✅ Actualizar campos de totales (usando los nuevos IDs)
    var subtotalField = document.getElementById('id_subtotal_display');
    var taxField = document.getElementById('id_tax_display');
    var totalField = document.getElementById('id_total_display');
    
    if (subtotalField) {
        subtotalField.value = subtotal.toFixed(2);
        console.log(`   ✅ Subtotal actualizado: ${subtotal.toFixed(2)}`);
    }
    if (taxField) {
        taxField.value = tax.toFixed(2);
        console.log(`   ✅ IVA actualizado: ${tax.toFixed(2)}`);
    }
    if (totalField) {
        totalField.value = total.toFixed(2);
        console.log(`   ✅ Total actualizado: ${total.toFixed(2)}`);
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

// ✅ Función para obtener precio y ubicación
function fetchProductDetails(productId, row) {
    if (!productId || productId === '') return;
    if (!row) return;
    
    console.log("🔴 Solicitando datos para producto:", productId);
    
    fetch('/admin/sales/get-product-price/?product_id=' + productId)
        .then(response => response.json())
        .then(data => {
            console.log("   Datos recibidos:", data);
            
            var priceInput = row.querySelector('input[name$="unit_price"]');
            if (priceInput) {
                priceInput.value = data.unit_price;
                priceInput.setAttribute('readonly', 'readonly');
                priceInput.style.backgroundColor = '#f0f0f0';
                priceInput.style.cursor = 'not-allowed';
                console.log("   ✅ Precio asignado:", data.unit_price);
            }
            
            var locationSelect = row.querySelector('select[name$="location"]');
            if (locationSelect && data.location_id) {
                for (var i = 0; i < locationSelect.options.length; i++) {
                    if (locationSelect.options[i].value == data.location_id) {
                        locationSelect.value = data.location_id;
                        console.log("   ✅ Ubicación asignada:", data.location_code);
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

// ✅ Configurar una fila
function setupRow(row) {
    console.log("🔴 Configurando fila");
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    var select = row.querySelector('select[id$="-product"]');
    
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
    console.log("🔴 Configurando todas las filas...");
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
    console.log("🔴 INICIALIZANDO...");
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

console.log("✅ Script cargado - VERSIÓN FINAL");