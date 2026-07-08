// django_erp/static/admin/js/sale_order_admin.js

console.log("🔴 SCRIPT CARGADO - VERSIÓN FINAL");

// ✅ Función para obtener precio y ubicación
function fetchProductDetails(productId, row) {
    if (!productId || productId === '') return;
    if (!row) return;
    
    console.log("🔴 Solicitando datos para producto:", productId);
    
    fetch('/admin/sales/get-product-price/?product_id=' + productId)
        .then(response => response.json())
        .then(data => {
            console.log("   Datos recibidos:", data);
            
            // ✅ Asignar precio
            var priceInput = row.querySelector('input[name$="unit_price"]');
            if (priceInput) {
                priceInput.value = data.unit_price;
                priceInput.setAttribute('readonly', 'readonly');
                priceInput.style.backgroundColor = '#f0f0f0';
                priceInput.style.cursor = 'not-allowed';
                console.log("   ✅ Precio asignado:", data.unit_price);
            }
            
            // ✅ Asignar ubicación y DESHABILITARLA
            var locationSelect = row.querySelector('select[name$="location"]');
            console.log("   Location select encontrado:", locationSelect);
            
            if (locationSelect && data.location_id) {
                // Buscar y seleccionar la ubicación
                for (var i = 0; i < locationSelect.options.length; i++) {
                    if (locationSelect.options[i].value == data.location_id) {
                        locationSelect.value = data.location_id;
                        console.log("   ✅ Ubicación asignada:", data.location_code);
                        break;
                    }
                }
                
                // ✅ DESHABILITAR el select de ubicación (no editable)
                locationSelect.disabled = true;
                locationSelect.style.backgroundColor = '#f0f0f0';
                locationSelect.style.cursor = 'not-allowed';
                console.log("   ✅ Ubicación deshabilitada (no editable)");
            }
            
            calculateSubtotal(row);
            updateTotals();
        })
        .catch(error => console.error("Error:", error));
}

// ✅ Función para calcular subtotal
function calculateSubtotal(row) {
    if (!row) return;
    
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    
    var qty = parseFloat(qtyInput?.value) || 0;
    var price = parseFloat(priceInput?.value) || 0;
    var subtotal = qty * price;
    
    var subtotalField = row.querySelector('.field-subtotal');
    if (subtotalField) {
        subtotalField.textContent = subtotal.toFixed(2);
    } else {
        var subtotalInput = row.querySelector('input[name$="subtotal"]');
        if (subtotalInput) {
            subtotalInput.value = subtotal.toFixed(2);
        }
    }
    
    updateTotals();
}

// ✅ Función para actualizar totales
function updateTotals() {
    var subtotal = 0;
    document.querySelectorAll('tr.form-row').forEach(function(row) {
        var qty = parseFloat(row.querySelector('input[name$="quantity"]')?.value) || 0;
        var price = parseFloat(row.querySelector('input[name$="unit_price"]')?.value) || 0;
        subtotal += qty * price;
    });
    
    var tax = subtotal * 0.19;
    var total = subtotal + tax;
    
    var subtotalField = document.getElementById('id_subtotal');
    var taxField = document.getElementById('id_tax');
    var totalField = document.getElementById('id_total');
    
    if (subtotalField) subtotalField.value = subtotal.toFixed(2);
    if (taxField) taxField.value = tax.toFixed(2);
    if (totalField) totalField.value = total.toFixed(2);
}

// ✅ Configurar una fila
function setupRow(row) {
    var select = row.querySelector('select[id$="-product"]');
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var locationSelect = row.querySelector('select[name$="location"]');
    
    // ✅ Si la ubicación ya tiene valor, deshabilitarla
    if (locationSelect && locationSelect.value && locationSelect.value !== '') {
        locationSelect.disabled = true;
        locationSelect.style.backgroundColor = '#f0f0f0';
        locationSelect.style.cursor = 'not-allowed';
    }
    
    // Configurar cantidad
    if (qtyInput && !qtyInput._hasEvents) {
        qtyInput._hasEvents = true;
        qtyInput.addEventListener('change', function() { 
            calculateSubtotal(row); 
        });
        qtyInput.addEventListener('keyup', function() { 
            calculateSubtotal(row); 
        });
    }
    
    // Configurar select de producto
    if (select && !select._hasEvents) {
        select._hasEvents = true;
        select._row = row;
        
        var $ = django.jQuery;
        
        $(select).on('select2:select', function(e) {
            var productId = e.params.data.id;
            if (productId && productId !== '') {
                var rowRef = this._row;
                this.value = productId;
                fetchProductDetails(productId, rowRef);
            }
        });
        
        select.addEventListener('change', function() {
            var productId = this.value;
            if (productId && productId !== '') {
                var rowRef = this._row;
                fetchProductDetails(productId, rowRef);
            }
        });
    }
}

// ✅ Configurar todas las filas
function setupAllRows() {
    document.querySelectorAll('tr.form-row').forEach(function(row) {
        setupRow(row);
    });
    updateTotals();
}

// ✅ Detectar nuevas filas
document.addEventListener('click', function(e) {
    var addButton = e.target.closest('.add-row a') || e.target.closest('.add-row');
    if (addButton || (e.target.textContent && e.target.textContent.includes('Agregar'))) {
        setTimeout(function() {
            document.querySelectorAll('tr.form-row').forEach(function(row) {
                if (!row._hasSetup) {
                    row._hasSetup = true;
                    setupRow(row);
                }
            });
            updateTotals();
        }, 200);
        setTimeout(setupAllRows, 500);
        setTimeout(setupAllRows, 1000);
    }
});

// ✅ Inicializar
setTimeout(setupAllRows, 500);
setTimeout(setupAllRows, 1500);
setTimeout(setupAllRows, 3000);

console.log("✅ Script cargado - Ubicación deshabilitada");