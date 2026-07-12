// django_erp/static/admin/js/sale_order_admin.js

console.log("🔴 SCRIPT CARGADO - VERSIÓN CON MONEDAS");

// ✅ Función para obtener precio y asignarlo
function fetchProductDetails(productId, row) {
    if (!productId || productId === '') return;
    if (!row) return;
    
    console.log("🔴 Solicitando datos para producto:", productId);
    
    fetch('/admin/sales/get-product-price/?product_id=' + productId)
        .then(response => response.json())
        .then(data => {
            console.log("   Datos recibidos:", data);
            
            // ✅ Buscar el input de precio
            var priceInput = row.querySelector('input[name$="unit_price"]');
            if (!priceInput) {
                priceInput = row.querySelector('input[id*="unit_price"]');
            }
            
            if (priceInput) {
                priceInput.value = data.unit_price;
                priceInput.setAttribute('readonly', 'readonly');
                priceInput.style.backgroundColor = '#f0f0f0';
                priceInput.style.cursor = 'not-allowed';
                console.log("   ✅ Precio asignado (USD):", data.unit_price);
                priceInput.dispatchEvent(new Event('change', { bubbles: true }));
            } else {
                // ✅ Mostrar precio en USD y BS en el campo de texto
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
                    console.log("   ✅ Precio mostrado en campo de texto:", data.unit_price);
                }
            }
            
            // ✅ Asignar ubicación
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
            
            // ✅ Recalcular subtotal y totales
            updateLineSubtotal(row);
            recalculateOrderTotals();
        })
        .catch(error => console.error("Error:", error));
}

// ✅ Función para actualizar subtotal de una línea
function updateLineSubtotal(row) {
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    
    // ✅ Si no encuentra el input, buscar el campo de texto
    if (!priceInput) {
        var priceDisplay = row.querySelector('.field-unit_price');
        if (priceDisplay) {
            var text = priceDisplay.textContent || '';
            // ✅ Buscar el primer número en el texto (precio en USD)
            var match = text.match(/\$?\s*(\d+\.?\d*)/);
            if (match) {
                var priceValue = parseFloat(match[1]);
                console.log("   Precio extraído del texto:", priceValue);
                updateTotalsFromValues(row, qtyInput, priceValue);
                return;
            }
        }
        console.log("   ❌ No se encontraron inputs de precio");
        return;
    }
    
    if (!qtyInput) {
        console.log("   ❌ No se encontró input de cantidad");
        return;
    }
    
    var qty = parseFloat(qtyInput.value) || 0;
    var price = parseFloat(priceInput.value) || 0;
    var subtotal = qty * price;
    
    console.log("   Subtotal calculado:", qty, "x", price, "=", subtotal);
    
    // Actualizar subtotal
    var subtotalField = row.querySelector('.field-subtotal');
    if (subtotalField) {
        subtotalField.textContent = subtotal.toFixed(2);
        console.log("   ✅ Subtotal actualizado en .field-subtotal");
    }
    
    var subtotalInput = row.querySelector('input[name$="subtotal"]');
    if (subtotalInput) {
        subtotalInput.value = subtotal.toFixed(2);
        console.log("   ✅ Subtotal actualizado en input");
    }
}

function updateTotalsFromValues(row, qtyInput, priceValue) {
    var qty = parseFloat(qtyInput?.value) || 0;
    var price = priceValue || 0;
    var subtotal = qty * price;
    
    console.log("   Subtotal calculado (fallback):", qty, "x", price, "=", subtotal);
    
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
                var match = text.match(/\$?\s*(\d+\.?\d*)/);
                if (match) {
                    price = parseFloat(match[1]) || 0;
                }
            }
        }
        
        var lineTotal = qty * price;
        subtotal += lineTotal;
    });
    
    var taxRate = 19;
    var tax = subtotal * (taxRate / 100);
    var total = subtotal + tax;
    
    // ✅ Obtener tasa de cambio
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
    
    // ✅ Actualizar campos en USD (2 decimales)
    var subtotalField = document.getElementById('id_subtotal_display');
    var taxField = document.getElementById('id_tax_display');
    var totalField = document.getElementById('id_total_display');
    
    if (subtotalField) subtotalField.value = subtotal.toFixed(2);
    if (taxField) taxField.value = tax.toFixed(2);
    if (totalField) totalField.value = total.toFixed(2);
    
    // ✅ Actualizar campos en Bs. (2 decimales)
    var subtotalBsField = document.getElementById('id_subtotal_bs_display');
    var taxBsField = document.getElementById('id_tax_bs_display');
    var totalBsField = document.getElementById('id_total_bs_display');
    
    if (subtotalBsField) {
        subtotalBsField.value = (subtotal * rate).toFixed(2);
        console.log("   ✅ Subtotal Bs.:", (subtotal * rate).toFixed(2));
    }
    if (taxBsField) {
        taxBsField.value = (tax * rate).toFixed(2);
        console.log("   ✅ IVA Bs.:", (tax * rate).toFixed(2));
    }
    if (totalBsField) {
        totalBsField.value = (total * rate).toFixed(2);
        console.log("   ✅ Total Bs.:", (total * rate).toFixed(2));
    }
}

// ✅ Configurar eventos
function setupRow(row) {
    console.log("🔴 Configurando fila");
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    var select = row.querySelector('select[id$="-product"]');
    var rowRef = row;
    
    // Hacer precio no editable
    if (priceInput && !priceInput.hasAttribute('readonly')) {
        priceInput.setAttribute('readonly', 'readonly');
        priceInput.style.backgroundColor = '#f0f0f0';
        priceInput.style.cursor = 'not-allowed';
    }
    
    // Configurar cantidad
    if (qtyInput) {
        console.log("   Cantidad encontrada");
        qtyInput.addEventListener('change', function() {
            console.log("🔴 Cambio en cantidad:", this.value);
            updateLineSubtotal(rowRef);
            recalculateOrderTotals();
        });
        qtyInput.addEventListener('keyup', function() {
            updateLineSubtotal(rowRef);
            recalculateOrderTotals();
        });
    }
    
    // Configurar select
    if (select) {
        console.log("   Select de producto encontrado");
        var $ = django.jQuery;
        
        $(select).on('select2:select', function(e) {
            var productId = e.params.data.id;
            console.log("🔴 Producto seleccionado (select2):", productId);
            if (productId) {
                this.value = productId;
                fetchProductDetails(productId, rowRef);
            }
        });
        
        select.addEventListener('change', function() {
            var productId = this.value;
            console.log("🔴 Producto seleccionado (change):", productId);
            if (productId) {
                fetchProductDetails(productId, rowRef);
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